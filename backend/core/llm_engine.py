"""Compatibility adapter; shares authorized demo Q&A and Knowledge Base retrieval."""
from services.support_answers import answer_question


def generate_ai_response(user_message, db, history=None, user=None, company_id=None):
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(401, 'Login required')
    # Legacy history is client-controlled and is never forwarded to Gemini.
    result = answer_question(user_message, db, user, company_id)
    return {'status': 'success', 'reply': result['answer'], 'mode': result['mode'],
            'source': result['source'], 'citations': result.get('citations', [])}
