from metadata_db import metadata_db
import abc

upload_queue = metadata_db.upload_queue
upload_success = metadata_db.upload_success


class Video(abc.ABC):
    def getAll():
        return (list(videos.upload_success.find({})))

    def insertOne(vid):
        return videos.upload_queue.insert(vid)
