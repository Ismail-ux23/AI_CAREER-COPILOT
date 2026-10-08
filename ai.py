from ollama import chat
import json
import os


def analyze_resume(resume_text, user_goal):
    prompt = f"""
You are a senior software engineer and hiring manager.

Analyze this resume for the goal: {user_goal}

Return only valid JSON with these keys:

{{
  "skills": ["list the skills found in the resume"],
  "missing_skills": ["list at least 5 important missing skills for this goal"],
  "roadmap": ["give 5 practical learning steps"],
  "interview_questions": ["give 5 interview questions"]
}}

Do not return empty lists. Generate useful answers for every key.

Resume:
{resume_text}
"""

    try:
        response = chat(
            model=os.getenv('OLLAMA_MODEL', 'llama3.2:1b'),
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict career manager. Return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.message.content.strip()
        start = content.find("{")
        end = content.rfind("}") + 1

        result = json.loads(content[start:end])
        required = ('skills', 'missing_skills', 'roadmap', 'interview_questions')
        if not isinstance(result, dict) or any(
            not isinstance(result.get(key), list)
            or any(not isinstance(item, str) for item in result[key])
            for key in required
        ):
            raise ValueError('Invalid career analysis response')
        return {key: result[key] for key in required}

    except Exception:
        return {
            "skills": [],
            "missing_skills": [],
            "roadmap": [],
            "interview_questions": [],
            "error": 'AI service unavailable or returned invalid analysis. Check Ollama and the configured model.'
        }
