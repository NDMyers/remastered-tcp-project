from customPacket import *

def signal_handler(signal,frame):
    print("exiting")
    sys.exit(0)

def getUserInput():
    host = str(sys.argv[1])
    port = int(sys.argv[2])
    return (host,port)

def start_dataSocket(dSock,myPacket):
    outPacket = tcpPacket(0) 
    dSock.settimeout(1)
    while True:
        try:
            outfile = open("result.txt",'a')
            # Receive data from sender and set header and payload accordingly 
            data,addr = dSock.recvfrom(1024) 
            outPacket.copyHeader(data); outPacket.setPayload(outPacket.getHeader()[17:])

            # If the received data contains a FIN, send back ACK then close connection
            if outPacket.getFin() == 1:
                print("Fin received!")
                myPacket.makeACKpkt(outPacket)
                dSock.sendto(myPacket,addr)
                dSock.close()
                break

            # Check how many bits sent at once for BDP
            pktLen = len(outPacket.getHeader()); payloadLen = len(outPacket.getPayload())
            cwndSize = outPacket.getCwnd()
            bitsSent = cwndSize*pktLen

            # Randomly drop or jitter the packet for simulation of connection issues
            BDP = 20000 # DELETE LATER. SHOULD COME FROM USER INPUT IN FINAL VER.
            jitter = 90 # SAME AS ABOVE
            pktLossPercentage = 10 # SAME AS ABOVE
            randomChance = random.randint(0,100)
            # Enter congestion state
            if bitsSent > BDP:
                if randomChance < (3*pktLossPercentage):
                    continue
                elif randomChance > jitter:
                    time.sleep(3*(randomChance/100))
            # Normal state
            elif bitsSent <= BDP:
                if randomChance < pktLossPercentage:
                    continue
                elif randomChance > jitter:
                    time.sleep(randomChance/100)
            # time.sleep(randomChance/100)
            #myPacket.setPayload("hello".encode()); myPacket.addPayload()

            # See if received packet is the correct one. If yes, then valid == true
            valid = (myPacket.verifySeqAck(outPacket))

            # Send ACK back to receiver
            if valid:
                print("valid")
                print(outPacket.getPayload().decode())
                outfile.write(outPacket.getPayload().decode())
                dSock.sendto(myPacket.getHeader(),addr)
                myPacket.incrementNums(myPacket.getPayload(),outPacket)

            # Repeat until correct packet is received
            else:
                print("not valid")
                


        except socket.timeout:
            print("Timeout ocurred...")

            if outPacket.getFin() == 1:
                print("Fin received!")
                myPacket.makeACKpkt(outPacket)
                dSock.sendto(myPacket,addr)
                dSock.close()
                break
            

def start_welcomeSocket(socketAddress):
    # Parse out address into individual variables
    host = socketAddress[0]; port = socketAddress[1]

    # Create 'welcoming' socket 
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as wSocket:

        # Create packet variables to be used throughout. 
        myPacket = tcpPacket(port); outPacket = tcpPacket(port)

        # Bind socket and get its newly created port number
        wSocket.bind(socketAddress)      # <-- can use (socketAddress) or (host,port). Same idea
        wSocketPort = wSocket.getsockname()[1]

        while True:
            try:
                # Take part in three-way handshake. (get SYN)
                data,addr = wSocket.recvfrom(1024)
                receiverPort = addr[1]
                outPacket.copyHeader(data)

                # Set and bind new data socket 
                dSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                dSock.bind( (host,0) )

                # Record new port to send to client so they can connect to it
                dSockPort = dSock.getsockname()[1]

                # Copy in header to tcpPacket(), reformat and change necessary values
                myPacket.makeSYNACKpkt(dSockPort,receiverPort,outPacket); myPacket.translateHeader()

                # Send response to sender's socket. (send SYN/ACK)
                wSocket.sendto(myPacket.getHeader(),addr)

                # Receive response from sender. (get ACK)
                data,addr = wSocket.recvfrom(1024)
                outPacket.copyHeader(data)

                # If 3-way successful. Start new thread for data socket for concurrent running sockets
                if outPacket.getAck() == 1:
                    dThread = threading.Thread(target=start_dataSocket,args=(dSock,myPacket,))
                    dThread.start()
                
            except:
                print("Error ocurred. 'Welcoming' socket disconnected.")
                break

def main():
    # Variable consisting of (host,port)
    socketAddress = getUserInput()

    # Threading to allow for multi-client connections 
    sockThread = threading.Thread(target=start_welcomeSocket,args=(socketAddress,))
    sockThread.start()

if __name__ == "__main__":
    main()