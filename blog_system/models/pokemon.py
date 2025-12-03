from database import Database
from datetime import datetime

class PokemonModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_global_stats(self):
        row = self.database.fetch_one("SELECT count FROM pokemon_interactions WHERE id = 1")
        return dict(row) if row else {"count": 0}

    def interact(self, user_id: int = None):
        # 增加全局点击数
        self.database.execute("UPDATE pokemon_interactions SET count = count + 1 WHERE id = 1")
        # 这里也可以扩展记录具体用户的互动
        return self.get_global_stats()