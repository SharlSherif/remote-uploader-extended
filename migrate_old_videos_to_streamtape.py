from video import Video
import asyncio
from wp_db import wp_db, cursor
videos = Video.getAll()
print(len(videos))
# ? change netu videos to streamtape
for video in videos:
    print(video['_id'], video['title'])
    cursor.execute(
        f"SELECT id FROM wp_posts where post_title = '{video['title']}'")
    wp_db.commit()
    records = cursor.fetchall()
    sql_id = records[0][0]
    cursor.execute(
        f"UPDATE wp_postmeta SET wp_postmeta.meta_value='{video['embed_code']}' WHERE wp_postmeta.post_id = '{sql_id}' AND wp_postmeta.meta_key ='embed'")

