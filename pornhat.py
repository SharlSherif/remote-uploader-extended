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
from pil import Image
from io import BytesIO
import base64
import re
from video import Video
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
import atexit
from selenium.webdriver.common.by import By

load_dotenv()

scraperAPI_KEY = os.environ.get('scraperAPI_KEY')
imgurAPI_KEY = os.environ.get('imgurAPI_KEY')
netuAPI_KEY = os.environ.get('netuAPI_KEY')
options = Options()
options.headless = True
browser = webdriver.Firefox(options=options)
class scraper:
    vid_details = []
    current_id = ''
    uploaded_data = list(Video.getAll())
    imgur_count = 0

    print(
        f"Total Previously Uploaded Videos is {len(uploaded_data)}")

    def img_to_base64_str(self, img):
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        buffered.seek(0)
        img_byte = buffered.getvalue()
        img_str = base64.b64encode(img_byte).decode()
        return img_str

    def convert_image_to_base64(self, image_direct_link):
        response = req.get(image_direct_link)
        img = Image.open(BytesIO(response.content))
        image_in_base64 = self.img_to_base64_str(img)

        return image_in_base64

    def upload_image_to_imgur(self, image_in_base64):
        if self.imgur_count >= 5:
            self.imgur_count = 0
            # sleep for 60 seconds
            print("GOING TO SLEEP ")
            time.sleep(120)
            print("WOKE UP..")

        headers = {'Authorization': "Client-ID "+imgurAPI_KEY}
        multipart_form_data = {
            'image':  (None, image_in_base64),
            'type': (None, 'base64')
        }

        r = req.post("https://api.imgur.com/3/image",
                     files=multipart_form_data, headers=headers)
        if r.json()['status'] == 400:
            self.imgur_count = 6
            raise Exception(r.json()['data']['error']['message'])
        else:
            self.imgur_count += 1
        print(r.json())
        return r.json()['data']['link']
    
    def upload_image_to_cdn(self, image_url,video_id):
        r = req.post(f"https://cdn.wildfaps.com/upload?url={image_url}&video_id={video_id}")
        if r.status_code != 200:
            raise Exception(r.json())
        print(r.json())
        return r.json()['url']

    def remote_upload(self, video_url):
        url = f"https://netu.tv/api/file/remotedl?key={netuAPI_KEY}&url={video_url}"
        response = req.get(url)
        file_temp_id= list(response.json()['result']['id'].keys())[0]
        isUploaded=False
        netu_file_code = ""
        while isUploaded== False:
            result = self.check_status(file_temp_id)
            if len(result) > 0:
                isUploaded=True
                netu_file_code = result
            else:
                print("Still uploading to netu..")
            time.sleep(10)
        embed_code = self.get_embed_code(netu_file_code)
        print("[SUCCESSFUL UPLOAD]")
        self.empty_queue(file_temp_id)
        return {'embed_code': embed_code, 'file_code':netu_file_code}

    def check_status(self, file_temp_id):
        url = f"https://netu.tv/api/file/status_remotedl?key={netuAPI_KEY}&id={file_temp_id}"
        response = req.get(url)
        if response.json()['result']['files'][file_temp_id]['status'] == 'successful':
            return response.json()['result']['files'][file_temp_id]['file_code']
        else: 
            return ""
    def empty_queue(self, file_temp_id):
        url = f"https://netu.tv/api/file/delete_remotedl?key={netuAPI_KEY}&id={file_temp_id}"
        response = req.get(url)
        print("[DELETED REMOTE QUEUE]")
        
    def get_embed_code(self, file_code):
        url = f"https://netu.tv/api/file/embed?key={netuAPI_KEY}&file_code={file_code}"
        response = req.get(url)
        return str(response.json()['result'][file_code]["embed_code_script"])

    def get_tags(self, vid_page_document):
        tags=[]
        tags_doc = list(vid_page_document.find("ul", class_="video-tags").children)
        for n in range(2, len(tags_doc)):
            try:
                tags.append(tags_doc[n].a.text)
            except Exception as e:
                pass
        return tags
    
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
        embed = str(vid['netu_embed_code'])
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

    async def open_vids_pages(self, count):
        print(f"[VIDEO] {count}")
        if count >= len(self.vid_details):
            print(f'[DONE] {len(self.vid_details)} videos were uploaded.')
            return self.vid_details

        video = self.vid_details[count]
        vid_page_url = video['source']
        
      
        
        browser.get(vid_page_url)
        WebDriverWait(browser, 50).until(expected_conditions.presence_of_element_located((By.TAG_NAME, "video"))) 
        vid_page_document = BeautifulSoup(
            browser.page_source, features="html.parser")

        title = vid_page_document.find("div",class_="title-holder").h1.text
        direct_url=None
        isHD=False
        download_link =  list(vid_page_document.find_all("a", class_="download-link"))
        video_url = (vid_page_document.find("video", class_="fp-engine")['src'])
        if download_link != None:
            direct_url = download_link.pop()['href']
            isHD=True
        else:
            direct_url = video_url
            
        description = vid_page_document.find("div", class_="desc")
        if description == None:
            description = ""
        else:
            description = description.text
             
        tags = self.get_tags(vid_page_document)
        duration = list(vid_page_document.find("ul", class_="video-meta").children)[3].text.replace(r" ", "")
        # image_in_base64 = self.convert_image_to_base64(video['thumbnail'])
        thumbnail_imgur_link = self.upload_image_to_cdn(video['thumbnail'], video['id'])
        title = title.replace(r"'", '')
        video = {
            "netu_embed_id": "",
            "title": title,
            "embed": "",
            "isHD": isHD,
            "direct_url":direct_url,
            "description": description,
            "duration": duration,
            "categories": [],
            "tags": tags,
            "thumbnail_imgur_link":thumbnail_imgur_link,
            **video
        }
        print(f"[UPLOADING] {direct_url}")
        isPosted = await self.is_posted_before(title)
        if isPosted == True:
            count = count+1
            return await self.open_vids_pages(count)
        
        netu_response = self.remote_upload(direct_url)
        video['netu_embed_code'] = netu_response['embed_code']
        video['netu_file_key'] = netu_response['file_code']
        video['netu_direct_url'] = f"https://waaw.to/f/{netu_response['file_code']}" 
        video['direct_url'] = direct_url
        video['google_drive'] = {"name": video['id'], "folderId":"17UbBSBUkM5ZMXMJrZRB9I6YZPJ-aR8pc", "folderName": "PO Data"}
        self.post_to_site(video)
        Video.insertOne(video)
        print("[STORED]")

        self.vid_details[count] = video
        count = count+1
        return await self.open_vids_pages(count)

    async def main(self):
        print("From Page : ")
        fromPage = int(input())
        print("To Page : ")
        toPage = int(input())
        time.sleep(2)
        #COmment this out
        # time.sleep(60*24)
        for n in range(fromPage, toPage):
            print(f"[PAGE] {n}")
            url = f"https://pornhat.com/{n}/"
            homepage = req.get(url)
            html = homepage.content.decode("utf-8")
            document = BeautifulSoup(html, features="html.parser")

            for thumb in document.findAll('div',class_='thumb-bl-video'):
                id = thumb.a['href'].replace("/video/", "").replace("/", "")
                print(id)
                isNew = True
                for video in self.uploaded_data:
                    if id == video['id']:
                        isNew = False
                if isNew == True:
                    vid_page_url = f"https://pornhat.com{thumb.a['href']}"
                    vid_thumbnail = thumb.a.img['data-original']
                    self.vid_details.append(
                        {'id': id, 'thumbnail': vid_thumbnail, 'source': vid_page_url})
                else:
                    print('[DUPLICATE] SKIPPING..')

        await asyncio.gather(self.open_vids_pages(0))

        # print("GOING TO POST VIDEOS")
        # for video in self.vid_details:
        #     print("POSTING VIDEO ", video)
        #     self.post_to_site(video)

    async def import_videos(self):
        previous_uploads = Video.getAll()
        print(len(previous_uploads))
        for video in previous_uploads:
            print("POSTING VIDEO ", video['title'])
            await self.post_to_site(video)

    async def checkDuplicates(self):
        previous_uploads = Video.getAll()
        shouldDeleteFromMongo=[]
        foundDups=[]
        print(len(previous_uploads))
        for video1 in previous_uploads:
            findCount = 0
            for video2 in previous_uploads:
                if video1['source'] == video2['source']:
                    findCount+=1
            if findCount > 1:
                foundDups.append(video1)

        for dup in foundDups:
            post = cursor.execute(
                f"SELECT ID FROM wp_posts where post_title='{dup['title']}' and post_parent=0;")
            wp_db.commit()
            post_id = cursor.fetchall()[0][0]
            cursor.execute(
            f"select * from wp_postmeta where post_id='{post_id}' and meta_key = 'thumb' and meta_value='{dup['thumbnail_imgur_link']}';")
            wp_db.commit()
            records = cursor.fetchall()
            if len(records) > 0:
                print(records)
            else:
                shouldDeleteFromMongo.append((dup['_id']))
        print(len(shouldDeleteFromMongo))
        print(shouldDeleteFromMongo)
        Video.deleteMany((shouldDeleteFromMongo))

    async def deleteNotStoredInWp(self):
        previous_uploads = Video.getAll()
        cursor.execute(f"SELECT post_title FROM wp_posts where post_parent=0;")
        wp_db.commit()
        posts_titles = cursor.fetchall()
        shouldDeleteFromMongo=[]
        for doc in previous_uploads:
            exists=False
            for title in posts_titles:
                if doc['title'] == (title[0]):
                    exists = True
            if exists == False:
                shouldDeleteFromMongo.append(doc['_id'])
        print(len(shouldDeleteFromMongo))
        Video.deleteMany((shouldDeleteFromMongo))

    async def test(self):
        vid = {"embed_id": "WjRnT1BDZ0hWVlRnMGp2TVNLdHoxQT09", "title": "Julia Rain \u2013 Intimate Casting", "embed": "https://hqq.to/e/WjRnT1BDZ0hWVlRnMGp2TVNLdHoxQT09", "description": "\u00a0", "duration": "\u00a0\u00a0100 min ", "categories": ["  Anal", " Blonde", " Blowjobs", " Clips", " Doggystyle"], "tags": ["Julia Rain ", "Rocco Siffredi"], "id": "364028", "thumbnail": "https://xxvideoss.org/wp-content/uploads/2020/04/456456450978645654.jpg", "source": "https://xxvideoss.org/julia-rain-intimate-casting/",
               "embed_code": "<div id=\"07b02207602203a02204707805105006e04806803107a05603406402207d\" style=\"height:450px;width:720px\"></div>\r\n<script src=\"data:text/javascript;base64,dmFyIHBhID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc2NyaXB0Jyk7IAp2YXIgcyA9IGRvY3VtZW50LmdldEVsZW1lbnRzQnlUYWdOYW1lKCdzY3JpcHQnKVswXTsgCiAgICBwYS5zcmMgPSAnaHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2xvYWRlcm1haW4uYXBwc3BvdC5jb20vbWFpbi5qcyc7CiAgICBzLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKHBhLCBzKTs=\"></script>"}
        self.post_to_site(vid)


sp = scraper()
loop = asyncio.get_event_loop()
# loop.run_until_complete(sp.import_videos())

# asyncio.ru(sp.import_videos())
loop.run_until_complete(sp.main())
# asyncio.ru(sp.main())
threading.Timer(2.0, sp.open_vids_pages).start()
threading.Timer(2.0, sp.import_videos).start()
threading.Timer(2.0, sp.is_posted_before).start()
def exit_handler():
    browser.quit()

atexit.register(exit_handler)