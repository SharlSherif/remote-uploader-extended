from metadata_db import metadata_db
import abc

videos = metadata_db.videos


class Video(abc.ABC):
    def getAll():
        return (list(videos.find({})))

    def insertOne(vid):
        return videos.insert(vid)
