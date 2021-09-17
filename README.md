## Intro
该库用于缓存某平台视频片段(ts文件)，并合并为mp4视频文件。
  > 注意: 脚本会把整个章节合并为1个视频文件，而非每小节

## Usage
- 安装python3
- 安装需求库
  `pip install -r requirments.txt`
- 配置文件config.json
  ```josn
  {
      "shop_id": "xxx",
      "course_id":  "xxx",
      "x_member":  "xxx",
      "start_time": 0,     # 每小节视频开头距离原视频开头的秒数
      "end_time": 0,       # 每小节视频结尾距离原视频结尾的秒数
      "stored_dir": null,  # 视频保存目录
      "process_number": 1  # 同时处理章节数目
  }
  ```
- `python downloader.py

## 免责声明
> 该库内容仅用于个人学习、研究或欣赏，以及其他非商业性或非盈利性用途。使用者应遵守著作权法及其他相关法律的规定，通过使用本站内容随之而来的风险与本人无关。
