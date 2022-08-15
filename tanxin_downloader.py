import os
import json
import time
import requests
from multiprocessing import Pool


class Downloader:

    def __init__(self, course_id, token, refresh_token, process_number=1, stored_dir=None):
        self.course_id = course_id
        self.token = token
        self.process_number = process_number
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
        self.headers = {
            'User-Agent': self.user_agent,
            'x-access-token': token,
            'x-refresh-token': refresh_token,
        }
        self.chapter_url = 'https://uai.greedyai.com/api/document/course/{}/user/catalog'.format(self.course_id)
        self.content_url = 'https://uai.greedyai.com/api/document/course/next'
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.stored_dir = stored_dir if isinstance(stored_dir, str) else os.path.join(self.current_dir, 'video')

    def prepare_dir(self):
        print('stored directory: {0}'.format(self.stored_dir))
        if not os.path.isdir(self.stored_dir):
            os.makedirs(self.stored_dir)

    @staticmethod
    def mkdir(p_dir, name):
        dir_path = os.path.join(p_dir, name)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    @staticmethod
    def get(url, headers, params, return_text=False, return_content=False):
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise
        if return_text:
            return response.text
        elif return_content:
            return response.content
        return response.json()

    def get_chapters(self):
        chapter_params = {
            't': int(time.time() * 1000),
        }
        return self.get(self.chapter_url, self.headers, chapter_params)

    def chapter_process(self, chapter, module_id, c_idx):
        chapter_title = chapter.get('chapterName')
        chapter_id = chapter.get('id')
        print('{0} start'.format(chapter_title))

        chapter_dir = self.mkdir(self.stored_dir, '{0}.{1}'.format(str(c_idx+1), chapter_title))

        for section_info in chapter.get('children', []):
            for group_info in section_info.get('children', []):
                section_id = group_info.get('id')
                content_params = {
                    "courseId": self.course_id,
                    "sectionId": section_id,
                    "chapterId": chapter_id,
                    "moduleId": module_id,
                    "update": True,
                    "userAnswer": "",
                    "appName": "UAI"
                }
                res = requests.post(self.content_url, headers=self.headers, json=content_params)
                content = res.json().get('data', {}).get('content', {})
                for idx, content_list in content.items():
                    for content_dict in content_list:
                        video_url = content_dict.get('page', {}).get('path', '')
                        video_title = content_dict.get('page', {}).get('title', '')
                        video_path_local = os.path.join(chapter_dir, '{0}.mp4'.format(video_title))
                        r = requests.get(video_url, stream=True)
                        print(video_path_local)
                        with open(video_path_local, 'wb') as video_file:
                            for chunk in r.iter_content(chunk_size=1024):
                                if chunk:
                                    video_file.write(chunk)

    def main_process(self, chapters, module_id):
        print('process count: {0}'.format(self.process_number))
        pool = Pool(self.process_number)
        for c_idx, chapter in enumerate(chapters):
            pool.apply_async(self.chapter_process, args=(chapter, module_id, c_idx))
        pool.close()
        pool.join()

    def video_download(self):
        print('Let the mission begin')

        self.prepare_dir()

        chapters_res = self.get_chapters()
        module_id = chapters_res.get('data').get('children')[0].get('id')
        chapters_list = chapters_res.get('data').get('children')[0].get('children')
        print('get chapters success')

        self.main_process(chapters_list, module_id)

        print('This mission is over')


if __name__ == '__main__':
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tanxin_config.json')
    with open(config_path, 'r') as f:
        configs = json.load(f)
    print('config load: {0}'.format(configs))
    downloader = Downloader(**configs)
    downloader.video_download()
