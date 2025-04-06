import os
import requests
import random
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Carica le variabili ambiente dal file .env
load_dotenv()
HUGGING_FACE_API_KEY = os.getenv("HUGGING_FACE_API_KEY")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache in memoria per evitare valutazioni duplicate
evaluation_cache = {}

def evaluate_idea(user_idea):
    """
    Richiede una valutazione completa dell'idea tramite l'API Hugging Face.
    Invia un prompt completo e restituisce solo il contenuto utile, rimuovendo il prompt iniziale.
    """
    headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}
    data = {
"inputs": (
        "You are a highly skilled startup evaluator with expertise in AI, business strategy, market analysis, and venture capital. "
        "Please perform a thorough and professional evaluation of the startup idea described below. Your assessment should be well-structured, "
        "insightful, and supported by data where possible. Be critical yet constructive. Your output should include the following sections:\n\n"

        "1. AI Judgment\n"
        "Provide a detailed and objective analysis of the startup idea. Highlight key strengths, potential weaknesses, internal inconsistencies, "
        "and technological feasibility. Discuss possible use of AI or advanced technologies, if relevant, and their implications on product viability and innovation.\n\n"

        "2. Market Analysis\n"
        "Offer a comprehensive overview of current market trends, customer demand, and timing. Identify and describe in deep main competitors or comparable players in the space. "
        "Highlight gaps, opportunities, and any competitive advantage the startup might leverage. Include real or estimated market size (TAM, SAM, SOM), supported necessairly by external data or charts. "
        "Provide graphs or visual aids to illustrate market dynamics, user growth potential, or competitive positioning.\n\n"

        "3. Business Plan\n"
        "Lay out a structured and detailed roadmap for execution and growth. This should include: \n"
        "    - Clear monetization strategy (e.g., freemium, subscription, B2B sales, etc.)\n"
        "    - Phases for MVP development, go-to-market strategy, customer acquisition, fundraising rounds (pre-seed to Series A/B, etc.), team scaling, and potential international expansion.\n"
        "    - A schematic, step-by-step breakdown of milestones and timeline for execution.\n"
        "    - Breakdown of costs, pricing, and revenue streams.\n"
        "    - Estimations of potential profit, funding needs, and risk analysis.\n"
        "    - Wherever applicable, present the financial forecast in tabular or graphical format for better clarity.\n\n"
        
        "Additionally, include any relevant charts, graphs, and data points that substantiate the analysis, showing growth projections, competitor performance, "
        "and market dynamics. Ensure the business plan is actionable and includes clear next steps for the startup to take in order to move forward.\n\n"

        "Note: The evaluation should not include the scoring criteria at the end of the business plan. "
        "The scoring (e.g., Creativity, Feasibility, Market Potential, Virality, Scalability) will be handled in a separate section outside this document.\n\n"
        
        f"Startup Idea: {user_idea}"
    ),
    "parameters": {
        "min_length": 100000
    }
}


    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct",
            headers=headers,
            json=data,
            timeout=60
        )
        if response.status_code == 401:
            error_msg = "Authorization Error: Please check your Hugging Face API key."
            logger.error(error_msg)
            return error_msg
        response.raise_for_status()
        result = response.json()
        generated_text = result[0].get("generated_text", "No evaluation provided by the AI.")
        logger.info("Generated text: %s", generated_text)
        
        # Rimuove il prompt dalla risposta: cerca "Startup Idea:" e poi "Strengths:" come indicazione dell'inizio del risultato utile
        idx = generated_text.lower().find("startup idea:")
        if idx != -1:
            idx_strengths = generated_text.lower().find("strengths:", idx)
            cleaned_text = generated_text[idx_strengths:] if idx_strengths != -1 else generated_text[idx + len("startup idea:"):].strip()
        else:
            cleaned_text = generated_text
        return cleaned_text
    except requests.exceptions.RequestException as e:
        error_msg = f"Request Error: {str(e)}"
        logger.error(error_msg)
        return error_msg

def parse_evaluation(evaluation):
    """
    Divide il testo generato in tre sezioni: AI Judgment, Market Analysis e Business Plan.
    Inoltre, genera dei punteggi casuali per cinque categorie e calcola un final score.
    """
    def extract_section(start_key, end_key=None):
        if start_key in evaluation:
            start = evaluation.find(start_key) + len(start_key)
            end = evaluation.find(end_key) if end_key and end_key in evaluation else None
            return evaluation[start:end].strip() if end else evaluation[start:].strip()
        return "Section not found."

    ai_judgment = extract_section("AI Judgment:", "Market Analysis:")
    market_analysis = extract_section("Market Analysis:", "Business Plan:")
    business_plan = extract_section("Business Plan:")

    aspects = {
        "Creativity": round(random.uniform(50, 100), 2),
        "Feasibility": round(random.uniform(50, 100), 2),
        "Market Potential": round(random.uniform(50, 100), 2),
        "Virality": round(random.uniform(50, 100), 2),
        "Scalability": round(random.uniform(50, 100), 2),
        "Time Needed": ""
    }
    text_lower = evaluation.lower()
    if "impossible" in text_lower or "difficult" in text_lower:
        aspects["Time Needed"] = f"{random.randint(5, 10)} years"
    elif "complex" in text_lower or "long-term" in text_lower:
        aspects["Time Needed"] = f"{random.randint(6, 18)} months"
    elif "simple" in text_lower or "quick" in text_lower:
        aspects["Time Needed"] = f"{random.randint(30, 120)} days"
    else:
        aspects["Time Needed"] = f"{random.randint(3, 12)} months"

    total = aspects["Creativity"] + aspects["Feasibility"] + aspects["Market Potential"] + aspects["Virality"] + aspects["Scalability"]
    final_score = total / 5
    if final_score < 60:
        final_score += 5
    final_score = min(final_score, 90)
    logger.info("Detailed evaluation aspects: %s", aspects)
    return aspects, final_score

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.get_json()
    user_idea = data.get("idea", "").strip()
    if not user_idea:
        return jsonify({"error": "No idea provided"}), 400

    if user_idea in evaluation_cache:
        return jsonify(evaluation_cache[user_idea])

    evaluation_text = evaluate_idea(user_idea)
    aspects, final_score = parse_evaluation(evaluation_text)

    response_data = {
        "evaluation": evaluation_text,
        "ai_judgement": evaluation_text.split("Market Analysis:")[0].strip() if "Market Analysis:" in evaluation_text else evaluation_text,
        "market_analysis": evaluation_text.split("Market Analysis:")[1].split("Business Plan:")[0].strip() if "Market Analysis:" in evaluation_text and "Business Plan:" in evaluation_text else "No market analysis provided.",
        "business_plan": evaluation_text.split("Business Plan:")[1].strip() if "Business Plan:" in evaluation_text else "No business plan provided.",
        "detailed_evaluation": aspects,
        "final_score": final_score
    }
    evaluation_cache[user_idea] = response_data
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
