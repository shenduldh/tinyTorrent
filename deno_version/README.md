这是一个 BitTorrent 的 tiny 实现（来自于 [cj1128/tinyTorrent](https://github.com/cj1128/tinyTorrent)），仅包含下载功能，未实现上传功能。使用方法如下：

```shell
$ deno run --allow-read --allow-net --allow-write ./main.ts <file.torrent> --debug
```
