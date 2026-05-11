# This is the persistence layer where the save methods are located.
# This layer will also handle an ongoing connection with Redis if provided.
# By default it will exist in local mode with a on disk file save path to temp.
# Redis/Local File will handle session information.
from abc import ABC, abstractmethod

class DataPersistence(ABC):
    @abstractmethod
    def __init__(self):
        self.persistence_type = "local" # Can be local|redis|custom
    
    @abstractmethod
    def save_data(self, key, data):
        pass

    @abstractmethod
    def retrieve_data(self, key):
        pass

class RedisPersistence(DataPersistence):
    def __init__(self, redis_url, redis_host):
        self.persistence_type = "redis"
    
    def save_data(self, key, data):
        pass
    
    def retrieve_data(self, key):
        pass

class LocalPersistence(DataPersistence):
    def __init__(self, local_file = "data.txt"):
        self.persistence_type = "local"
        self.local_file = local_file
    
    def save_data(self, key, value):
        value.replace("\n", "\\n")

        with open(self.local_file, "a+") as f:
            f.seek(0)
            data = f.readlines()

        with open(self.local_file, "r") as f:
            data = f.readlines()

        for i, line in enumerate(data):
            if key == line.split(":", 1)[0].strip():
                data[i] = f"{key}: {value}\n"
                with open(self.local_file, "w") as f:
                    f.writelines(data)
                return
        
        data.append(f"{key}: {value}\n")

        with open(self.local_file, "w") as f:
            f.writelines(data)

    def retrieve_data(self, key):
        with open(self.local_file, "r") as f:
            data = f.readlines()

        for line in data:
            if key == line.split(":", 1)[0].strip():
                value = line.split(":", 1)[1].strip()
                value.replace("\\n", "\n")
                return value
        
        return None