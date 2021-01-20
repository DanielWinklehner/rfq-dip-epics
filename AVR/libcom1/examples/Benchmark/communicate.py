import time
import serial

port = '/dev/ttyACM0'
baud = 115200

# Replace 'A' with 'q10a10a20b30b46c56c16d26d35e46e56' for comm_lib
lines = ['q01a10\n', 'q01a13\n', 'q01a16\n',
 'q01a20\n', 'q01a23\n', 'q01a26\n', 
 'q01b30\n', 'q01b33\n', 'q01b36\n', 
 'q01b40\n', 'q01b43\n', 'q01b46\n', 
 'q01c50\n', 'q01c53\n', 'q01c56\n', 
 'q01c10\n', 'q01c13\n', 'q01c16\n', 
 'q01d20\n', 'q01d23\n', 'q01d26\n', 
 'q01d30\n', 'q01d33\n', 'q01d36\n', 
 'q01e40\n', 'q01e43\n', 'q01e46\n',
 'q01e50\n', 'q01e53\n', 'q01e56\n', 
 'sa11\n', 'sa22\n',
 'sb33\n', 'sb44\n',
 'sc55\n', 'sc11\n',
 'sd22\n', 'sd33\n',
 'se44\n', 'se55\n',
 'A\n']

with serial.Serial(port, baud, timeout=1) as ser:
    for line in lines:
        writeline = line.encode('ascii')
        
        print(f'Communicating on {ser.name} with baud rate {baud} and writing: {writeline.decode("utf-8").rstrip()}')

        # Wall clock time  
        begin = time.time()

        line = b''              
        itr = 0
        while line != b'EOF\n':  
            ser.write(writeline)
            line = ser.readline()
            
            itr += 1
            print(itr, end='\r')
            l = line.decode('utf-8')
            if (l[0] != 'o'):
                print(l)

        print( 'Arduino: {}'.format(ser.readline().decode("utf-8").rstrip() ))
        print( 'Completed communication in {}s'.format(time.time() - begin))

