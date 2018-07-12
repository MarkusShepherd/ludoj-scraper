#!/usr/bin/env bash

set -euo pipefail

JOBSDIR='jobs'
STATE_FILE='.state'

function find_state() {
	DELETE=${3:-''}

	for DIR in "$1"/*; do
		# echo "$DIR"

		if [[ -d "$DIR" && -f "$DIR/$STATE_FILE" && "$(cat "$DIR/$STATE_FILE")" == "$2" ]]; then
			basename "$DIR"

			if [[ -n "$DELETE" ]]; then
				rm -rf "$DIR"
			fi
		fi
	done
}

mkdir -p logs
mkdir -p "$JOBSDIR"

DATE=$(date --utc +'%Y-%m-%dT%H-%M-%S')

for SCRAPER in $(scrapy list); do
	JOBDIR="$JOBSDIR/$SCRAPER"

	DELETED=$(find_state "$JOBDIR" 'finished' 'true')

	if [[ -n "$DELETED" ]]; then
		echo "Deleted finished jobs in <$JOBDIR>: $DELETED."
	fi

	if [[ -n "$(find_state "$JOBDIR" 'running')" ]]; then
		echo "Found a running job, skipping <$SCRAPER>..."
		continue
	fi

	JOBTAG="$DATE"
	SHUT_DOWN="$(find_state "$JOBDIR" 'shutdown')"

	if [[ -n "$SHUT_DOWN" ]]; then
		JOBTAG="$(echo "$SHUT_DOWN" | tr -d ' \n')"
		echo "Resuming previous job <$JOBTAG> for spider <$SCRAPER>."
	else
		echo "Starting new job for spider <$SCRAPER>."
	fi

	nohup scrapy crawl "$SCRAPER" \
		-o 'feeds/%(name)s/%(time)s/%(class)s.csv' \
		-s "JOBDIR=jobs/$SCRAPER/$JOBTAG" \
		>> "logs/$SCRAPER.log" 2>&1 &

	echo "Started! Follow logs from <$(pwd)/logs/$SCRAPER.log>."
done
