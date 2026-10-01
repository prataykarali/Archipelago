import os

class Config:
    def __init__(self):
        # Environment
        self.ENV = os.environ.get("FLASK_ENV", "development")
        
        # Database
        self.DB_PATH = os.environ.get("DB_PATH", "okf_graph.db")
        self.JSON_PATH = os.environ.get("JSON_PATH", "okf_graph.json")
        
        # Auth
        self.SUPABASE_URL = os.environ.get("SUPABASE_URL")
        self.SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
        
        # Inference
        self.INFERENCE_UPSTREAM = os.environ.get("INFERENCE_UPSTREAM", "http://localhost:11434")
        
        # Rate Limiting
        self.RATE_LIMIT_DISABLED = os.environ.get("ARCHIPELAGO_RATE_LIMIT_DISABLED") == "1"
        self.RATE_LIMIT_PER_MIN = int(os.environ.get("ARCHIPELAGO_RATE_LIMIT_PER_MIN", "20"))
        
        # Caching
        self.CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
        self.CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "300"))
        
        # Logging
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        
    def is_production(self):
        return self.ENV == "production"
        
    def is_development(self):
        return self.ENV == "development"
        
    def get_db_path(self):
        return self.DB_PATH
        
    def validate(self):
        if self.is_production():
            if not self.SUPABASE_URL or not self.SUPABASE_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY are required in production")
                
config = Config()
