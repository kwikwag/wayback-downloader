import os
import sys
import errno
import urllib
import urllib2
from urlparse import urlparse
import time
from datetime import datetime
from collections import deque
from multiprocessing import Pool

USAGE = """Usage:
	python <script.py> {--help|-h}
	python <script.py> [--matchType {exact|prefix|host|domain}] [--from <timestamp>] [--to <timestamp] [--limit <snapshots>] <url>

Options:
	--help, -h		Display this help message and exit

	--matchType, -m	What results will be downloaded based on <url>
		exact		Download results matching exactly <url>
		prefix		Download results under the path <url>
		host		Download results from host of <url>
		domain		Download results from host of <url> and all subhosts of <url>

	--from, -f		Download results that were captured after this timestamp
	--to, -t		Download results that were captured before this timestamp
		Both <from> and <to> must be a prefix of "yyyyMMddhhmmss"

	--limit, -l		Download at most <snapshots> snapshots

Example:
	Use the following command:
		python <script.py> --matchType prefix --from 2010 --to 201606 --limit 1000 example.org
	To download at most 1000 abarity pages under example.org between the year of 2010 and the month of June 2016 (inclusive).

For more information, see: https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md"""

THREADS = 10

def write(response, filename, timestamp):
	directory = os.path.dirname(filename)
	if not os.path.exists(directory):
		try:
			os.makedirs(directory)
		except OSError as e:
			if e.errno != errno.EEXIST:
				return False
	with open(filename, "wb") as file:
		year = int(timestamp[:4])
		month = int(timestamp[4:6])
		day = int(timestamp[6:8])
		hour = int(timestamp[8:10])
		minute = int(timestamp[10:12])
		second = int(timestamp[12:14])
		timestamp = datetime(year, month, day, hour, minute, second)
		file.write(response.read())
		os.utime(filename, (time.time(), time.mktime(timestamp.timetuple())))
		return True
	return False

def download(row):
	urlkey, timestamp, original, mimetype, statuscode, digest, length = row
	parsed = urlparse(urllib.unquote(original))
	domain = parsed.netloc.split(':')[0]
	filename = os.path.join(os.path.dirname(sys.argv[0]), domain, parsed.path.lstrip('/'))
	url = "http://web.archive.org/web/{}if_/{}".format(timestamp, original)
	response = None
	
	try:
		response = urllib2.urlopen(url)
		if response.getcode() == 200:
			return write(response, filename, timestamp)
	except urllib2.URLError as e:
		return False
	except urllib2.HTTPError as e:
		return False
	finally:
		if response is not None:
			response.close()

def download_all(**params):
	response = None
	try:
		response = urllib2.urlopen("http://web.archive.org/cdx/search/cdx?" + urllib.urlencode(params))
		if response.getcode() == 200:
			rows = [line.split() for line in response]
	except urllib2.URLError as e:
		return False
	except urllib2.HTTPError as e:
		return False
	finally:
		if response is not None:
			response.close()
	total = len(rows)
	unique = set()
	rows = [unique.add(row[2]) or row for row in rows if row[2] not in unique]
	duplicates = total - len(rows)
	print "Downloading {} snapshot{}...{}".format(len(rows), "" if len(rows) == 1 else "s", " (removed {} duplicate{})".format(duplicates, "" if duplicates == 1 else "s") if duplicates else "")
	total = len(rows)
	pool = Pool(THREADS)
	while rows:
		i = 0
		for success in pool.imap(download, rows):
			urlkey, timestamp, original, mimetype, statuscode, digest, length = rows[i]
			if success:
				del rows[i]
			else:
				i += 1
			count = total - len(rows)
			print "\r{}/{} ({:.2f}%)".format(count, total, 100.0 * count / total),
			# print "\r{}/{} ({:.2f}%), {} failed.".format(count, total, 100.0 * count / total, i),

def parseargs(argv):
	if not argv or "--help" in argv or "-h" in argv:
		return None
	args = {
		"matchType": ["--matchType", "-m"],
		"from": ["--from", "-f"],
		"to": ["--to", "-t"],
		"limit": ["--limit", "-l"]
	}
	params = {}
	for arg, names in args.iteritems():
		for name in names:
			if name in argv:
				index = argv.index(name)
				argv.pop(index)
				value = argv.pop(index)
				params[arg] = value
	if len(argv) > 1:
		return None
	params["url"] = argv.pop()
	return params

def main():
	params = parseargs(sys.argv[1:])
	if params is None:
		print USAGE.replace("<script.py>", sys.argv[0])
		sys.exit(1)

	download_all(**params)
	sys.exit(0)

if __name__ == "__main__":
	main()