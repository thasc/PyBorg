import pyborg

# note - this is based on a specific IRC log format
# [HH:mm:SS] <name> Message!
# adjust timestamp_offset if needed to remove the timestamp and get:
# <name> Message!
# then the script will handle the rest

file = '/home/you/logs.txt'
timestamp_offset = 11

def main(pyborg):
	num_lines_processed = 0
	with open(file) as log:
		for line in log:
			print 'Processing line ' + str(num_lines_processed+1)
			line = line[timestamp_offset:] # remove timestamp
			if line[:1] != '<': # messages only
				continue
			name_end = line.index('>')
			line = line[name_end+2:] # remove name
			if line[:1] not in '!,':
				try:
					pyborg.process_msg(None, line, 0, 1, None, owner = 1)
					num_lines_processed = num_lines_processed + 1
				except AttributeError:
					print 'Couldn\'t read line ' + line
					raise
	print num_lines_processed

if __name__ == "__main__":
    # start the pyborg
    my_pyborg = pyborg.pyborg()
    try:
        main(my_pyborg)
    except SystemExit:
        pass
    my_pyborg.save_all()
    del my_pyborg

