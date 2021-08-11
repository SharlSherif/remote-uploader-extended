from video import Video
import asyncio
from pornhat import scraper
from wp_db import wp_db, cursor

videos = Video.getAll()
print(len(videos))
sp = scraper()

for video in videos:
    if video['player_type'] == 'netu' and 'iframe' not in video['embed_code']:
        print(video['_id'], video['title'])
        result = sp.remote_upload_streamtape(video['original_video_url'])
        embed_code=result['embed_code']
        Video.updateOne(video['_id'],{'$rename':{'embed_code':'netu_embed_code'}})
        Video.updateOne(video['_id'],{'$set':{'embed_code':embed_code,}})
        cursor.execute(
            f"SELECT id FROM wp_posts where post_title = '{video['title']}'")
        wp_db.commit()
        records = cursor.fetchall()
        sql_id = records[0][0]
        cursor.execute(
            f"UPDATE wp_postmeta SET wp_postmeta.meta_value='{embed_code}' WHERE wp_postmeta.post_id = '{sql_id}' AND wp_postmeta.meta_key ='embed'")