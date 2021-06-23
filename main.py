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

load_dotenv()

scraperAPI_KEY = os.environ.get('scraperAPI_KEY')
imgurAPI_KEY = os.environ.get('imgurAPI_KEY')
netuAPI_KEY = os.environ.get('netuAPI_KEY')

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
        # image_direct_link = 'https://i.imgur.com/53c4v4g.jpg'
        response = req.get(image_direct_link)
        im = Image.open(BytesIO(response.content))
        # Size of the image in pixels (size of orginal image)
        # (This is not mandatory)
        width, height = im.size

        # Setting the points for cropped image
        left = 0
        top = 0
        right = width
        bottom = 3 * height / 4

        # Cropped image of above dimension
        # (It will not change orginal image)
        image_modified = im.crop((left, top, right, bottom))
        # print(BytesIO(image_modified))
        image_in_base64 = self.img_to_base64_str(image_modified)

        return image_in_base64

    def upload_image_to_imgur(self, image_in_base64):
        if self.imgur_count >= 6:
            self.imgur_count = 0
            # sleep for 60 seconds
            print("GOING TO SLEEP ")
            time.sleep(60)
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
            print(r.json()['data'])
            raise Exception(r.json()['data']['error']['message'])
        else:
            self.imgur_count += 1

        return r.json()['data']['link']

    def remote_upload(self, embed_id):
        print("embed_id ", embed_id)
        url = f"https://netu.tv/api/file/clone?key={netuAPI_KEY}&file_code={embed_id}&del_orig=0"
        response = req.get(url)
        print("[SUCCESSFUL UPLOAD]")
        netu_file_code = response.json()['result']['file_code']
        embed_code = self.get_embed_code(netu_file_code)
        return {'embed_code': embed_code, 'file_code':netu_file_code}

    def get_embed_code(self, file_code):
        url = f"https://netu.tv/api/file/embed?key={netuAPI_KEY}&file_code={file_code}"
        response = req.get(url)
        return str(response.json()['result'][file_code]["embed_code_script"])

    def get_categories(self, vid_page_document):
        categories = []
        for div in vid_page_document.find_all('span'):
            if 'class' in div.attrs:
                for c in div.attrs['class']:
                    if c == 'cat-links':
                        categories = div.text.split('|')[0].split(',')
                        categories[0] = clean_str(
                            categories[0].replace("Categories", " "))
        return categories

    def get_tags(self, vid_page_document):
        tags = []
        for div in vid_page_document.find_all('span'):
            if 'class' in div.attrs:
                for c in div.attrs['class']:
                    if c == 'tag-links':
                        tags = div.text.split('|')[0].split('#')
                        del tags[0]
        return tags

    def post_to_site(self, vid):
        print(vid)
        cursor.execute(
            f"SELECT * FROM wp_posts where post_title = '{vid['title']}'")
        wp_db.commit()
        records = cursor.fetchall()

        if len(records) > 0:
            print("video was posted before ", vid)
            return
        # get last post id
        cursor.execute(
            "SELECT id FROM wp_posts WHERE id = (SELECT MAX(id) FROM wp_posts);")

        last_post = cursor.fetchone()
        last_post_id = None
        if (last_post) == None:
            last_post_id = 0
        else:
            last_post_id = last_post[0]
        print(last_post_id)
        # calculating duration
        # numb = [int(i) for i in vid['duration'].split() if i.isdigit()]
        numb = [210]
        # static
        post_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        future_post_id = last_post_id+1
        # dynamic
        post_title = str(vid['title'])
        duration = numb[0] * 60
        post_name = vid['source'].replace(
            'https://xxvideoss.org/', '').replace('/', '')
        embed = str(vid['netu_embed_code'])
        post_content = re.sub('\s[^0-9a-zA-Z]+', '', str(vid['description']))
        print(post_content)
        # ? modify the thumbnail to remove the xxvideos.org logo
        thumbnail = vid['thumbnail']
        image_in_base64 = self.convert_image_to_base64(thumbnail)
        thumbnail_imgur_link = self.upload_image_to_imgur(image_in_base64)
        print(post_name)
        # handles if there's a description for the video or not.
        if len(post_content) > 0:
            cursor.execute(f"""
                INSERT INTO wp_posts
                (post_author,post_title, post_content, post_date,post_modified, post_modified_gmt, post_date_gmt, post_excerpt, to_ping, pinged, post_content_filtered, post_status, comment_status, ping_status, post_name, post_parent, guid, post_type) VALUES
                (1,'{post_title}','{post_content}','{post_date}', '{post_date}', '{post_date}','{post_date}', '','','', '','publish', 'open', 'open', '{post_name}', 0, 'https://hdpornh.com/?p={future_post_id}', 'post');
            """)
        else:
            # created the post
            cursor.execute(f"""
                    INSERT INTO wp_posts
                    (post_author,post_title, post_content, post_date,post_modified, post_modified_gmt, post_date_gmt, post_excerpt, to_ping, pinged, post_content_filtered, post_status, comment_status, ping_status, post_name, post_parent, guid, post_type) VALUES
                    (1,'{post_title}','','{post_date}','{post_date}','{post_date}','{post_date}', '', '','','','publish', 'open', 'open', '{post_name}', 0, 'https://hdpornh.com/?p={future_post_id}', 'post');
            """)

        # now create the "revision" version of the post
        cursor.execute(f"""
                INSERT INTO wp_posts
                (post_author,post_title, post_content, post_date, post_modified,post_modified_gmt, post_date_gmt, post_excerpt, to_ping, pinged, post_content_filtered, post_status, comment_status, ping_status, post_name, post_parent, guid, post_type) VALUES
                (1,'{post_title}','','{post_date}', '{post_date}','{post_date}', '{post_date}', '','','','', 'publish', 'open', 'open', '{future_post_id}-revision-v1', {future_post_id}, 'https://hdpornh.com/hqporner/{future_post_id}-revision-v1/', 'revision');
        """)
        print(future_post_id)
        # video thumbnail
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'thumb', '{thumbnail_imgur_link}');")

        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', '_pingme', 1);")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'embed', '{embed}');")
        cursor.execute(
            f"INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES ('{future_post_id}', 'hd_video', 'on');")
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
            print(tag)
            print(len(records), records)
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
                print('just saved and retrieved this : ', records)
                tag_id = (records[0][0])
                # save that tag in wp_term_taxonomy
                cursor.execute(
                    f"INSERT INTO wp_term_taxonomy (term_id, taxonomy, description) VALUES ({tag_id},'post_tag','');")
            cursor.execute(
                f"SELECT * FROM wp_term_taxonomy WHERE term_id = '{tag_id}';")
            wp_db.commit()
            records = cursor.fetchall()
            term_taxonomy_id = (records[0][0])
            print(term_taxonomy_id)
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
            print(category)
            print(len(records), records)
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
                print('just saved and retrieved this : ', records)
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
            print(term_taxonomy_id)
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
        vid_page = req.get(vid_page_url)
        vid_page_html = vid_page.content.decode("utf-8")
        vid_page_document = BeautifulSoup(
            vid_page_html, features="html.parser")

        # vid_index = self.vid_details.index(find(self.vid_details, current_id))
        # print(vid_index)

        # print(video['id'])
        # print(vid_page_document.h1.text)  # ? title
        # print(vid_page_document.iframe['src'])  # ? embed
        iframes = vid_page_document.findAll('iframe')
        embed = None
        for iframe in iframes:
            if 'hqq.to' in iframe['src']:
                embed = iframe['src']
        print(embed)
        # embed = vid_page_document.iframe['src']
        duration = ''
        description = ''
        categories = self.get_categories(vid_page_document)
        tags = self.get_tags(vid_page_document)

        for div in vid_page_document.find_all('div'):
            if 'class' in div.attrs:
                for c in div.attrs['class']:
                    if c == 'entry-content':
                        all_p = div.find_all('p')
                        if len(all_p) > 1:
                            description = div.find_all(
                                'p')[1].text  # ? description
                        else:
                            description = ''
                        for x in div.find_all('p'):
                            if 'Duration' in x.text:
                                duration = x.text.split('|')[1]  # ? duration
                                print(duration)
        if ('https://hqq.to/e/' in embed) == False:
            print("NOT A NETU VIDEO")
            count = count+1
            return await self.open_vids_pages(count)

        video = {
            "netu_embed_id": embed.replace("https://hqq.to/e/", ""),
            "title": clean_str(vid_page_document.h1.text.replace(r"\u", "")),
            "embed": embed,
            "description": clean_str(description.replace(r"\u", "")),
            "duration": duration.replace("Duration:", ''),
            "categories": categories,
            "tags": tags,
            **video
        }
        print(f"[UPLOADING] {video['netu_embed_id']}")
        netu_response = self.remote_upload(video['netu_embed_id'])
        video['netu_embed_code'] = netu_response['embed_code']
        video['netu_file_key'] = netu_response['file_code']
        video['netu_direct_url'] = f"https://waaw.to/f/{netu_response['file_code']}" 
        try:
            self.post_to_site(video)
            Video.insertOne(video)
            print("[STORED]")

        except Exception as e:
            print("ERROR ", str(e))

        self.vid_details[count] = video
        count = count+1
        return await self.open_vids_pages(count)

    async def main(self):
        print("From Page : ")
        fromPage = int(input())
        print("To Page : ")
        toPage = int(input())
        time.sleep(2)
        for n in range(fromPage, toPage):
            print(f"[PAGE] {n}")
            # http://api.scraperapi.com?api_key={scraperAPI_KEY}&url=
            url = f"https://xxvideoss.org/page/{n}"
            homepage = req.get(url)
            html = homepage.content.decode("utf-8")
            document = BeautifulSoup(html, features="html.parser")
            isNew = True
            for article in document.findAll('article'):
                id = article['id'].replace("post-", "")
                for video in self.uploaded_data:
                    if id == video['id']:
                        isNew = False
                if isNew == True:
                    vid_page_url = article.a['href']
                    vid_thumbnail = article.div.img['src']
                    self.vid_details.append(
                        {'id': id, 'thumbnail': vid_thumbnail, 'source': vid_page_url})
                else:
                    print('[DUPLICATE] SKIPPING..')

        await asyncio.gather(self.open_vids_pages(0))

        print("GOING TO POST VIDEOS")
        for video in self.vid_details:
            print("POSTING VIDEO ", video)
            self.post_to_site(video)

    async def import_videos(self):
        previous_uploads = json.load(open(uploaded_file_path, "r"))
        print(len(previous_uploads))
        for video in previous_uploads:
            print("POSTING VIDEO ", video)
            self.post_to_site(video)

    async def test(self):
        vid = {"embed_id": "WjRnT1BDZ0hWVlRnMGp2TVNLdHoxQT09", "title": "Julia Rain \u2013 Intimate Casting", "embed": "https://hqq.to/e/WjRnT1BDZ0hWVlRnMGp2TVNLdHoxQT09", "description": "\u00a0", "duration": "\u00a0\u00a0100 min ", "categories": ["  Anal", " Blonde", " Blowjobs", " Clips", " Doggystyle"], "tags": ["Julia Rain ", "Rocco Siffredi"], "id": "364028", "thumbnail": "https://xxvideoss.org/wp-content/uploads/2020/04/456456450978645654.jpg", "source": "https://xxvideoss.org/julia-rain-intimate-casting/",
               "embed_code": "<div id=\"07b02207602203a02204707805105006e04806803107a05603406402207d\" style=\"height:450px;width:720px\"></div>\r\n<script src=\"data:text/javascript;base64,dmFyIHBhID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc2NyaXB0Jyk7IAp2YXIgcyA9IGRvY3VtZW50LmdldEVsZW1lbnRzQnlUYWdOYW1lKCdzY3JpcHQnKVswXTsgCiAgICBwYS5zcmMgPSAnaHR0cHM6Ly9zdG9yYWdlLmdvb2dsZWFwaXMuY29tL2xvYWRlcm1haW4uYXBwc3BvdC5jb20vbWFpbi5qcyc7CiAgICBzLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKHBhLCBzKTs=\"></script>"}
        self.post_to_site(vid)


sp = scraper()
loop = asyncio.get_event_loop()
loop.run_until_complete(sp.main())

asyncio.ru(sp.main())
threading.Timer(2.0, sp.open_vids_pages).start()
