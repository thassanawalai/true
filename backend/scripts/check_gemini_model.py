"""Explicit single model metadata check; never runs inference or enables Gemini."""
import argparse
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True,
                        help='Make one Google API metadata request using local key/model')
    parser.parse_args()
    load_dotenv(backend / '.env')
    if not os.getenv('GEMINI_API_KEY') or not os.getenv('GEMINI_MODEL'):
        print('Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env first. Values hidden.')
        return 1
    from services.gemini_support import new_client
    client = None
    try:
        client = new_client()
        model = client.models.get(model=os.environ['GEMINI_MODEL'])
        if 'generateContent' not in (model.supported_actions or []):
            print('Configured model does not advertise generateContent. Keep Gemini disabled.')
            return 1
        print('Configured model is accessible and advertises generateContent. No inference performed.')
        print('Inference quota, structured output support, and Thai answer quality remain unverified.')
        return 0
    except Exception:
        print('Model metadata check failed. Check key/model/access privately; keep Gemini disabled.')
        return 1
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    sys.exit(main())
