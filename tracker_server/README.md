如果需要自行制作种子进行测试，可按以下步骤进行：

1. 从 [webtorrent/bittorrent-tracker](https://github.com/webtorrent/bittorrent-tracker) 安装和运行 tracker；

   ```shell
   $ npm install bittorrent-tracker
   $ npx bittorrent-tracker
   ```

2. 利用 [BitComet](https://www.bitcomet.com/en)（或其他可以做种的软件） 制作一个 torrent 文件（tracker 的地址填写为步骤 1 安装的 tracker），并保持做种（上传）状态。