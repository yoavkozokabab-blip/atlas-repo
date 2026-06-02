class FileWriter:
    def __init__(self, path):
        self.path = path
        self.overwrite = True

    def write(self, text):
        with open(self.path, "w" if self.overwrite else "a", encoding="utf-8") as output_file:
            output_file.write(text)
        self.overwrite = False
