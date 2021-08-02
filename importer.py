import requests as req
from datetime import datetime
import sys
from bs4 import BeautifulSoup
import threading
import asyncio
import json
from threading import Thread
import time
import os
from wp_db import wp_db, cursor
from helpers import is_in_array, find, clean_str
from metadata_db import metadata_db
from io import BytesIO
import base64
import re
from video import Video
import atexit

class scraper:
    vid_details = []
    current_id = ''
    uploaded_data = list(Video.getAll())
    imgur_count = 0

    print(
        f"Total Previously Uploaded Videos is {len(uploaded_data)}")

    async def is_posted_before (self, title):
        cursor.execute(
        f"SELECT * FROM wp_posts where post_title = '{title}'")
        wp_db.commit()
        records = cursor.fetchall()

        if len(records) > 0:
            print("video was posted before ", title)
            return True
        else:
            return False
    async def post_to_site(self, vid):
        isPosted = await self.is_posted_before(vid['title'])
        if isPosted == True:
            return False
        # get last post id
        cursor.execute(
            "SELECT id FROM wp_posts WHERE id = (SELECT MAX(id) FROM wp_posts);")

        last_post = cursor.fetchone()
        last_post_id = None
        if (last_post) == None:
            last_post_id = 0
        else:
            last_post_id = last_post[0]
        # calculating duration
        duration = int(vid['duration'].split(":")[0]) * 60
        # static
        post_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        future_post_id = last_post_id+1
        # dynamic
        post_title = str(vid['title'])
        post_name = vid['source'].replace(
            'https://pornhat.com/', '').replace('/', '')
        if len(post_name) > 200:
            post_name = post_name[1:200]
        embed = str(vid['embed_code'])
        post_content = re.sub('\s[^0-9a-zA-Z]+', '', str(vid['description']))
        post_content = post_content.replace(r"'", '').replace("Description: ","")
        # ? modify the thumbnail to remove the xxvideos.org logo
        thumbnail_imgur_link = vid['thumbnail_imgur_link']
        # handles if there's a description for the video or not.
        if len(post_content) > 0:
            cursor.execute(f"""
                INSERT INTO wp_posts
                (post_author,post_title, post_content, post_date,post_modified, post_modified_gmt, post_date_gmt, post_excerpt, to_ping, pinged, post_content_filtered, post_status, comment_status, ping_status, post_name, post_parent, guid, post_type) VALUES
                (1,'{post_title}','{post_content}','{post_date}', '{post_date}', '{post_date}','{post_date}', '','','', '','publish', 'open', 'open', '{post_name}', 0, 'https://wildfaps.com/?p={future_post_id}', 'post');
            """)
        else:
            # created the post
            cursor.execute(f"""
                    INSERT INTO wp_posts
                    (post_author,post_title, post_content, post_date,post_modified, post_modified_gmt, post_date_gmt, post_excerpt, to_ping, pinged, post_content_filtered, post_status, comment_status, ping_status, post_name, post_parent, guid, post_type) VALUES
                    (1,'{post_title}','','{post_date}','{post_date}','{post_date}','{post_date}', '', '','','','publish', 'open', 'open', '{post_name}', 0, 'https://wildfaps.com/?p={future_post_id}', 'post');
            """)

        # now create the "revision" version of the post
        cursor.execute(f"""
                INSERT INTO wp_posts
                (post_author,post_title, post_content, post_date, post_modified,post_modified_gmt, post_date_gmt, post_excerpt, to_ping, pinged, post_content_filtered, post_status, comment_status, ping_status, post_name, post_parent, guid, post_type) VALUES
                (1,'{post_title}','','{post_date}', '{post_date}','{post_date}', '{post_date}', '','','','', 'publish', 'open', 'open', '{future_post_id}-revision-v1', {future_post_id}, 'https://wildfaps.com/hqporner/{future_post_id}-revision-v1/', 'revision');
        """)

        HD_status = "on"
        if vid['isHD'] == False:
            HD_status = "off"
        # video thumbnail
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'thumb', '{thumbnail_imgur_link}');")

        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', '_pingme', 1);")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'embed', '{embed}');")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'hd_video', '{HD_status}');")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'duration', {duration});")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'post_views_count', 0);")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'likes_count', 0);")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', '_encloseme', 1);")

        wp_db.commit()

        primary_seo_category_id = None

        for tag in vid['tags']:
            tag = clean_str(" ".join(tag.split()))
            cursor.execute(f"select * from wp_terms where name = '{tag}'")
            wp_db.commit()
            records = cursor.fetchall()
            tag_id = None
            term_taxonomy_id = None
            if len(records) > 0:  # that tag is already saved
                tag_id = (records[0][0])
            else:  # tag doesn't exist, i need to create it
                tag_slug = ''.join(tag.lower().replace(r' ', '-'))
                cursor.execute(
                    f"INSERT INTO wp_terms (name, slug, term_group) VALUES ('{tag}','{tag_slug}',0);")
                cursor.execute(
                    f"SELECT * FROM wp_terms WHERE name = '{tag}';")
                wp_db.commit()
                records = cursor.fetchall()
                tag_id = (records[0][0])
                # save that tag in wp_term_taxonomy
                cursor.execute(
                    f"INSERT INTO wp_term_taxonomy (term_id, taxonomy, description) VALUES ({tag_id},'post_tag','');")
            cursor.execute(
                f"SELECT * FROM wp_term_taxonomy WHERE term_id = '{tag_id}';")
            wp_db.commit()
            records = cursor.fetchall()
            term_taxonomy_id = (records[0][0])
            # now make the relationship between the post and the tag given their ids (object_id is actually the post id in this case)
            cursor.execute(
                f"INSERT INTO wp_term_relationships (object_id, term_taxonomy_id, term_order) VALUES ({future_post_id},{term_taxonomy_id},0);")
            wp_db.commit()

        for category in vid['categories']:
            category = clean_str(" ".join(category.split()))
            cursor.execute(
                f"select * from wp_terms where name = '{category}'")
            wp_db.commit()
            records = cursor.fetchall()
            category_id = None
            term_taxonomy_id = None
            if len(records) > 0:  # that category is already saved
                category_id = (records[0][0])
            else:  # category doesn't exist, i need to create it
                category_slug = ''.join(category.lower().replace(r' ', '-'))
                cursor.execute(
                    f"INSERT INTO wp_terms (name, slug, term_group) VALUES ('{category}','{category_slug}',0);")
                cursor.execute(
                    f"SELECT * FROM wp_terms WHERE name = '{category}';")
                wp_db.commit()
                records = cursor.fetchall()
                category_id = (records[0][0])
                # save that category in wp_term_taxonomy
                cursor.execute(
                    f"INSERT INTO wp_term_taxonomy (term_id, taxonomy, description) VALUES ({category_id},'category','');")

            # im saving the category_id for the first category in the list to use later as a primary seo category

            if is_in_array(vid['categories'], category) == 0:
                primary_seo_category_id = category_id
                print('CATEGORY FOUND')
            cursor.execute(
                f"SELECT * FROM wp_term_taxonomy WHERE term_id = '{category_id}';")
            wp_db.commit()
            records = cursor.fetchall()
            term_taxonomy_id = (records[0][0])
            # now make the relationship between the post and the category given their ids (object_id is actually the post id in this case)
            try:
                cursor.execute(
                    f"INSERT INTO wp_term_relationships (object_id, term_taxonomy_id, term_order) VALUES ({future_post_id},{term_taxonomy_id},0);")
                print("MAIN CATEGORY ID == ", primary_seo_category_id)
                wp_db.commit()
            except Exception:
                pass

        # # ! remove this later
        # exit(0)
        # ? this part for the seo main category, should be added later
        # INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', '_yoast_wpseo_primary_category', 3);

        # add the post meta
        if primary_seo_category_id == None:
            # if no categories were found, add the id of "HD Pornhub Videos" as a default category
            primary_seo_category_id = 1
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', '_yoast_wpseo_primary_category', {primary_seo_category_id});")

        # cursor.execute(f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'bialty_cs_alt', '');")
        # cursor.execute(
        #     f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'featured_video', 'on');")

        wp_db.commit()

    async def import_videos(self):
        previous_uploads = Video.getAll()+ Video.getAllFromQueue()
        print(len(previous_uploads))
        for video in previous_uploads:
            print("POSTING VIDEO ", video['title'])
            await self.post_to_site(video)


sp = scraper()
loop = asyncio.get_event_loop()
loop.run_until_complete(sp.import_videos())

threading.Timer(2.0, sp.import_videos).start()
threading.Timer(2.0, sp.is_posted_before).start()