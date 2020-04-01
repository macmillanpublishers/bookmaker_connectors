from sys import argv 

count = 0
for arg in argv:
	count += 1
	print("argv{}: {}".format(count, arg))
