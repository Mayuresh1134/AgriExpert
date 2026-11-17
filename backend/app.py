"""Start the AgriExpert API (and the built frontend, if frontend/dist exists)."""
from agri import create_app
from agri.config import Config

app = create_app()

if __name__ == "__main__":
    print(f"AgriExpert running on http://localhost:{Config.PORT}  (database: {Config.DB_MODE}, "
          f"assistant: {'Gemini' if Config.GEMINI_API_KEY else 'built-in'})")
    app.run(host="0.0.0.0", port=Config.PORT, debug=False, threaded=True)
