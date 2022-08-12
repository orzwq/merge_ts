import os
import json
import m3u8
import shutil
import requests
from Crypto.Cipher import AES
from multiprocessing import Pool


# 短书
class Downloader:

    def __init__(self, shop_id, course_id, x_member, start_time=0, end_time=0, stored_dir=None, process_number=1):
        self.shop_id = shop_id
        self.course_id = course_id
        self.x_member = x_member
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
        self.headers = {
            'User-Agent': self.user_agent,
            'x-member': self.x_member
        }
        self.simple_headers = {
            'User-Agent': self.user_agent,
            'Origin': 'https://zeafv.duanshu.com',
            'Referer': 'https://zeafv.duanshu.com/',
        }
        self.chapter_url = 'https://api.duanshu.com/fairy/api/v1/courses/{0}/chapters/'.format(self.course_id)
        self.detail_url = 'https://api.duanshu.com/h5/content/course/class/detail'
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.stored_dir = stored_dir if isinstance(stored_dir, str) else os.path.join(self.current_dir, 'video')
        self.start_time = start_time
        self.end_time = end_time
        self.process_number = process_number

    def prepare_dir(self):
        print('stored directory: {0}'.format(self.stored_dir))
        if not os.path.isdir(self.stored_dir):
            os.makedirs(self.stored_dir)

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
            'id': self.course_id,
            'size': 999,
            'shop_id': self.shop_id
        }
        return self.get(self.chapter_url, self.headers, chapter_params)

    def get_class_detail(self, class_id):
        detail_params = {
            'course_id': self.course_id,
            'class_id': class_id,
            'shop_id': self.shop_id
        }

        res = self.get(self.detail_url, self.headers, detail_params)
        video_path = res.get('response', {}).get('content', {}).get('video_patch', '')
        token = res.get('response', {}).get('content', {}).get('token', '')
        return video_path, token

    @staticmethod
    def mkdir(p_dir, name):
        dir_path = os.path.join(p_dir, name)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    @staticmethod
    def merge_ts(chapter_dir, video_name, ts_path_list):
        rows = ['file ' + ts_path + '\n' for ts_path in ts_path_list]
        write_file = os.path.join(chapter_dir, 'ts_list.txt')
        with open(write_file, 'w') as f:
            f.writelines(rows)
        output_file = os.path.join(chapter_dir, '{0}.mp4'.format(video_name))
        command = 'ffmpeg -f concat -safe 0 -i {0} -c copy {1}'.format(write_file, output_file)
        os.system(command)
        print('merge ts files success, video path: {0}'.format(output_file))

    def chapter_process(self, chapter):
        chapter_title = chapter.get('title')
        print('{0} start'.format(chapter_title))

        if len(chapter.get('class_content')) == 0:
            print('empty class, {0} end'.format(chapter_title))
            return

        chapter_dir = self.mkdir(self.stored_dir, chapter_title)

        chapter_idx = 0
        for class_info in chapter.get('class_content'):
            class_title = class_info.get('title')
            print('{0}-{1} start'.format(chapter_title, class_title))
            # class_dir = self.mkdir(chapter_dir, class_title)

            class_id = class_info.get('id')
            video_path, token = self.get_class_detail(class_id)

            m3u8_obj = m3u8.load(video_path)

            key = m3u8_obj.keys[0]
            aes_key = self.get(key.uri, self.simple_headers, {'token': token}, return_content=True)
            cryptor = AES.new(aes_key, AES.MODE_CBC, bytes.fromhex(key.iv.replace('0x', '')))

            length = len(m3u8_obj.segments)
            min_idx = 0
            max_idx = length - 1
            start_sum = 0
            for i in range(length):
                start_sum = start_sum + m3u8_obj.segments[i].duration
                if start_sum > self.start_time:
                    min_idx = i
                    break
            end_sum = 0
            for j in range(length - 1, -1, -1):
                end_sum = end_sum + m3u8_obj.segments[j].duration
                if end_sum >= self.end_time:
                    max_idx = j
                    break
            ts_path_list = []
            for idx, segment in enumerate(m3u8_obj.segments):
                if min_idx <= idx < max_idx:
                    chapter_idx += 1
                    stored_path = os.path.join(chapter_dir, '{0}.ts'.format(str(chapter_idx).rjust(3, '0')))
                    content = self.get(segment.absolute_uri, self.simple_headers, {}, return_content=True)
                    with open(stored_path, 'wb') as f:
                        f.write(cryptor.decrypt(content))
                    ts_path_list.append(stored_path)

            print('{0}-{1} end'.format(chapter_title, class_title))

        self.merge_ts(chapter_dir, chapter_title, ts_path_list)
        print('{0} end'.format(chapter_title))

    def main_process(self, chapters):
        print('process count: {0}'.format(self.process_number))
        pool = Pool(self.process_number)
        for chapter in chapters:
            pool.apply_async(self.chapter_process, args=(chapter, ))
        pool.close()
        pool.join()

    def video_download(self):
        print('Let the mission begin')

        self.prepare_dir()

        chapters_res = self.get_chapters()
        chapters_list = chapters_res.get('response').get('data')
        print('get chapters success')

        self.main_process(chapters_list)

        print('This mission is over')


if __name__ == '__main__':
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    with open(config_path, 'r') as f:
        configs = json.load(f)
    print('config load: {0}'.format(configs))
    downloader = Downloader(**configs)
    downloader.video_download()



