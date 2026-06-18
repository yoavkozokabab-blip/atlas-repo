class AuthStore:
    def login(self, token: str) -> bool:
        return bool(token)
