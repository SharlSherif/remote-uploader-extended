from video import Video
import asyncio

videos = Video.getAll()
print(len(videos))
# for video in videos:
#     if 'player_type' not in video:
#         Video.updateOne(video['_id'],{'$set':{'player_type':'netu'}})
#     else:
#         print('streamtape')


async def fix ():
    for video in videos:
        if video['player_type']== 'netu':
            print(video['player_type'])
            Video.updateOne(video['_id'],{'$rename':{'netu_embed_code':'embed_code', 'netu_file_key':'file_key', 'netu_direct_url':'player_direct_url', 'direct_url':'original_video_url' }, })
            print('updated')
        else:
            print('streamtape')

asyncio.run(fix())