from metadata_db import metadata_db
import abc

upload_queue = metadata_db.upload_queue
upload_success = metadata_db.upload_success


class Video(abc.ABC):
    def getAll():
        return (list(upload_success.find({})))

    def getAllFromQueue():
        return (list(upload_queue.find({})))

    def updateOne(_id, vid):
        return upload_success.update_one({"_id":_id}, vid)
    def insertOne(vid):
        return upload_queue.insert(vid)

    def deleteMany(ids):
        return upload_success.delete_many({"_id": {"$in": ids}})
