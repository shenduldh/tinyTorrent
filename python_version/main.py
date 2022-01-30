from client.downloader import Downloader
from utils.log import Printer

Printer.level = 1

TORRENT_FILE_PATH = '../assets/test.torrent'
SAVED_FILE_PATH = './'
EXTRA_TRACKERS_PATH = './tracker.txt'

downloader = Downloader(TORRENT_FILE_PATH, SAVED_FILE_PATH)
downloader.get_torrent()
downloader.fetch_peers()
downloader.start()
