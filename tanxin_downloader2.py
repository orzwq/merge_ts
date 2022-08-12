import os
import re
import json
import time
import m3u8
import requests
from Crypto.Cipher import AES
from multiprocessing import Pool


# 贪心科技
class Downloader:

    def __init__(self, course_id, token, refresh_token, cookie, site_id,
                 process_number=1, stored_dir=None, ts_stored_dir=None):
        self.course_id = course_id
        self.token = token
        self.site_id = site_id
        self.process_number = process_number
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
        self.headers = {
            'User-Agent': self.user_agent,
            'x-access-token': token,
            'x-refresh-token': refresh_token,
            'Cookie': cookie,
        }
        self.simple_headers = {
            'User-Agent': self.user_agent,
            'Origin': 'https://uai.greedyai.com',
            'Referer': 'https://uai.greedyai.com',
        }
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.ts_stored_dir = ts_stored_dir if isinstance(ts_stored_dir, str) \
            else os.path.join(self.current_dir, 'ts_video')
        self.stored_dir = stored_dir if isinstance(stored_dir, str) else os.path.join(self.current_dir, 'video')
        self.plans = 'https://uai.greedyai.com/course/api/course/user/course/{0}/'.format(self.course_id)
        self.live_content_url = 'https://uai.greedyai.com/course/api/course/user/live/{0}/{1}/liveContent'
        self.video_file_url = 'https://p.bokecc.com/servlet/getvideofile'
        self.custom_callback = 'cc_jsonp_callback_507336'

    def prepare_dir(self):
        print('stored directory: {0}'.format(self.stored_dir))
        print('ts stored directory: {0}'.format(self.ts_stored_dir))
        if not os.path.isdir(self.stored_dir):
            os.makedirs(self.stored_dir)
        if not os.path.isdir(self.ts_stored_dir):
            os.makedirs(self.ts_stored_dir)

    @staticmethod
    def mkdir(p_dir, name):
        dir_path = os.path.join(p_dir, name.replace(' ', '-'))
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
    
    @staticmethod
    def get_time_dict():
        return {'t': int(time.time() * 1000)}

    def get_plans(self):
        return self.get(self.plans, self.headers, self.get_time_dict())

    @staticmethod
    def merge_ts(base_dir, video_name, write_file):
        output_file = os.path.join(base_dir, '{0}.mp4'.format(video_name))
        command = 'ffmpeg -f concat -safe 0 -i {0} -c copy "{1}"'.format(write_file, output_file)
        os.system(command)
        print('merge ts files success, video path: {0}'.format(output_file))

    def plan_process(self, plan, c_idx):
        plan_name = plan.get('planName', 'unknown')
        print('{0} start'.format(plan_name))

        plan_dir = self.mkdir(self.ts_stored_dir, '{0}.{1}'.format(str(c_idx+1), plan_name))
        video_plan_dir = self.mkdir(self.stored_dir, '{0}.{1}'.format(str(c_idx+1), plan_name))

        for p_idx, part in enumerate(plan.get('parts', [])):
            part_id = part.get('id')
            part_name = part.get('partName', 'unknown')
            part_dir = self.mkdir(plan_dir, '{0}.{1}'.format(str(p_idx+1), part_name))
            video_part_dir = self.mkdir(video_plan_dir, '{0}.{1}'.format(str(p_idx+1), part_name))

            print('{0}-{1} start'.format(plan_name, part_name))

            live_content = self.get(self.live_content_url.format(self.course_id, part_id),
                                    self.headers, self.get_time_dict())

            for v_idx, recorded_page in enumerate(live_content.get('data', {}).get('recordedPages', [])):
                vid = recorded_page.get('page', {}).get('vid')
                title = recorded_page.get('page', {}).get('title')
                if not isinstance(vid, str):
                    print('vid empty: {0}-{1}-{2}'.format(plan_name, part_name, title))
                    continue

                print('{0}-{1}-{2} start'.format(plan_name, part_name, title))
                video_dir = self.mkdir(part_dir, '{0}.{1}'.format(str(v_idx + 1), title))
                # final_video_dir = self.mkdir(video_part_dir, '{0}.{1}'.format(str(v_idx + 1), title))

                params = {
                    'vid': vid,
                    'siteid': self.site_id,
                    'width': '100%',
                    'useragent': 'other',
                    'version': '20140214',
                    'hlssupport': '1',
                    'callback': self.custom_callback,
                }

                m3u8_url_info_str = self.get(self.video_file_url, {}, params, return_text=True)

                if not isinstance(m3u8_url_info_str, str):
                    print('m3u8_url_info_str empty: {0}-{1}-{2}'.format(plan_name, part_name, title))
                    continue

                m3u8_url_info = json.loads(
                    re.match(r'{0}\((.*)\)'.format(self.custom_callback), m3u8_url_info_str).group(1))

                copies_list = m3u8_url_info.get('copies', [])

                if len(copies_list) == 0:
                    print('copies_list empty: {0}-{1}-{2}'.format(plan_name, part_name, title))
                    continue

                m3u8_url = copies_list[-1].get('playurl')

                if not isinstance(m3u8_url, str):
                    print('m3u8_url empty: {0}-{1}-{2}'.format(plan_name, part_name, title))
                    continue

                # print(m3u8_url)

                m3u8_obj = m3u8.load(m3u8_url)
                key = m3u8_obj.keys[0]
                aes_key = self.get(key.uri, self.simple_headers, {}, return_content=True)
                cryptor = AES.new(aes_key, AES.MODE_CBC, bytes.fromhex(key.iv.replace('0x', '')))

                ts_path_list = []
                for idx, segment in enumerate(m3u8_obj.segments):
                    stored_path = os.path.join(video_dir, '{0}.ts'.format(str(idx+1).rjust(5, '0')))
                    content = self.get(segment.absolute_uri, self.simple_headers, {}, return_content=True)
                    with open(stored_path, 'wb') as f:
                        f.write(cryptor.decrypt(content))
                    ts_path_list.append(stored_path)

                rows = ['file ' + ts_path + '\n' for ts_path in ts_path_list]
                write_file = os.path.join(video_dir, 'ts_list.txt')
                with open(write_file, 'w') as f:
                    f.writelines(rows)

                self.merge_ts(video_part_dir, title, write_file)

                print('{0}-{1}-{2} end'.format(plan_name, part_name, title))

                # break

    def main_process(self, plans):
        print('process count: {0}'.format(self.process_number))

        # 多进程处理
        # pool = Pool(self.process_number)
        # for c_idx, plan in enumerate(plans):
        #     pool.apply_async(self.plan_process, args=(plan, c_idx))
        # pool.close()
        # pool.join()

        # 单进程处理
        for c_idx, plan in enumerate(plans):
            self.plan_process(plan, c_idx)

    def video_download(self):
        print('Let the mission begin')

        self.prepare_dir()

        plans_res = self.get_plans()
        # print(plans_res)

        plans = plans_res.get('data').get('plans', [])
        print('get plans success')

        self.main_process(plans)

        print('This mission is over')


if __name__ == '__main__':
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tanxin_config2.json')
    with open(config_path, 'r') as f:
        configs = json.load(f)
    print('config load: {0}'.format(configs))
    downloader = Downloader(**configs)
    downloader.video_download()
