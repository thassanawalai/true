"""Run analysis and live portal regressions against a disposable local PostgreSQL.
Requires PostgreSQL server binaries (pg_config --bindir). Never uses backend/.env.
The temporary cluster and HTTP server are stopped in finally; only synthetic data.
Run from backend: .venv/bin/python scripts/test_security_postgres.py
"""
import os, pathlib, secrets, socket, subprocess, sys, tempfile, time, unittest, urllib.request
from unittest.mock import patch

backend = pathlib.Path(__file__).resolve().parents[1]
pgbin = subprocess.check_output(['pg_config', '--bindir'], text=True).strip() + '/'
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    http_port = listener.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='soc-analysis-pg-') as root:
    data = str(pathlib.Path(root) / 'data')
    def pg(*args):
        subprocess.run([pgbin + args[0], *args[1:]], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    pg('initdb', '-D', data, '-A', 'trust', '--no-locale', '-E', 'UTF8')
    pg('pg_ctl', '-D', data, '-l', root + '/postgres.log', '-o', f"-k {root} -p 55439 -c listen_addresses=''", '-w', 'start')
    server = None
    try:
        os.environ.update(DATABASE_URL=f'postgresql+psycopg2:///postgres?host={root}&port=55439',
            PYTHON_DOTENV_DISABLED='1', GEMINI_ENABLED='false', GEMINI_API_KEY='',
            DEMO_SESSION_SECRET=secrets.token_urlsafe(32), PYTHONWARNINGS='ignore')
        os.chdir(backend)
        sys.path[:0] = [str(backend), str(backend / 'tests')]
        from main import app
        from core.database import Base, engine
        from sqlalchemy import create_engine
        import test_gemini_offline as fixture
        import test_security_analysis
        def postgres_fixture(*args, **kwargs):
            isolated = create_engine(os.environ['DATABASE_URL'])
            Base.metadata.drop_all(isolated)
            return isolated
        with patch.object(fixture, 'create_engine', side_effect=postgres_fixture):
            result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_security_analysis))
        print('POSTGRES_ANALYSIS_PASS=', result.wasSuccessful(), flush=True)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        import runpy
        runpy.run_path(str(backend / 'scripts/seed_phase1.py'))
        server_log = open(root + '/uvicorn.log', 'w')
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(http_port)], stdout=server_log, stderr=server_log)
        for _ in range(100):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{http_port}/', timeout=1).close()
                if server.poll() is not None:
                    raise RuntimeError('Isolated server exited during startup')
                break
            except Exception:
                if server.poll() is not None:
                    raise RuntimeError('Isolated server startup failed')
                time.sleep(.1)
        import test_chat_rooms, test_portal_api
        original = urllib.request.Request
        def request(url, *args, **kwargs):
            return original(url.replace('127.0.0.1:8000', f'127.0.0.1:{http_port}'), *args, **kwargs)
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (test_chat_rooms, test_portal_api))
        with patch.object(test_chat_rooms, 'Request', request), patch.object(test_portal_api, 'Request', request):
            live_result = unittest.TextTestRunner(verbosity=2).run(suite)
        print('POSTGRES_LIVE_PASS=', live_result.wasSuccessful(), flush=True)
        success = result.wasSuccessful() and live_result.wasSuccessful()
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
            server_log.close()
        pg('pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop')
    sys.exit(not success)
