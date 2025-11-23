ls -1 | while read file; do echo $file ; mkvinfo $file | grep "Title:" ; done
