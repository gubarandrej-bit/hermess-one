class DatabaseManager:
    def __init__(self, url):
        self.url = url
    def get_all_users(self): return []
    def create_user(self, u, p, r): return {"status": "ok"}
    def delete_user(self, id): return True
