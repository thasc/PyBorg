import sys
import pyborg

# note - this is based on a specific IRC log format
# [HH:mm:SS] <name> Message!
# adjust timestamp_offset if needed to remove the timestamp and get:
# <name> Message!
# then the script will handle the rest

def main(pyborg, file, timestamp_offset):
    num_lines_processed = 0
    print 'Starting feed with ' + file + ' and ' + str(timestamp_offset)
    with open(file) as log:
        for line in log:
            print 'Processing line ' + str(num_lines_processed+1)
            line = line[timestamp_offset:] # remove timestamp
            if line[:1] != '<': # messages only
                continue
            while line[:1] == '<' and '>' in line:
                name_end = line.index('>')
                line = line[name_end+2:] # remove name
            if line[:1] not in '!,':
                try:
                    pyborg.process_msg(None, line, 0, 1, None, owner=1)
                    num_lines_processed = num_lines_processed + 1
                except AttributeError:
                    print 'Couldn\'t read line ' + line
                    raise
    print num_lines_processed

if __name__ == "__main__":
    logfile = sys.argv[1]
    timestamp_offset = sys.argv[2]
    if not logfile:
        print 'No file specified!'
	if not timestamp_offset:
		print 'No timestamp offset specified!'
    my_pyborg = pyborg.pyborg()
    try:
		main(my_pyborg, logfile, int(timestamp_offset))
    except SystemExit:
        pass
    my_pyborg.save_all()
    del my_pyborg
