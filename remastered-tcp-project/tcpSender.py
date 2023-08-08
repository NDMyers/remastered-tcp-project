from customPacket import *

# Global variable for adjusting max size a packet can be
pktSize = 1000
# Accompanying array that stores said individual packets
packets = []

def getUserInput():
    # Error prevention for user input
    if (len(sys.argv) != 9 or sys.argv[1] != "--server_ip" or 
            sys.argv[3] != "--server_port" or sys.argv[5] != "--tcp_version"
            or sys.argv[7] != "--input"):
        print("usage: python3 tcpSender.py --server_ip XXXX.XXXX.XXXX.XXXX --server_port YYYY --tcp_version tahoe/reno --input input.txt")
        sys.exit(0)
        
    host = str(sys.argv[2])
    port = int(sys.argv[4])
    tcp_version = str(sys.argv[6].lower())
    txt = sys.argv[8]

    # Error prevention for tcp version tahoe/reno input
    if tcp_version != "tahoe".lower() and tcp_version != "reno".lower():
        print("Invalid TCP version entered.")
        print("usage: python3 client_putah.py --server_ip XXXX.XXXX.XXXX.XXXX --server_port YYYY --tcp_version tahoe/reno --input input.txt")
        sys.exit(0)

    if tcp_version != "tahoe".lower() and tcp_version != "reno".lower():
        print("Invalid TCP version entered.")
        print("usage: python3 client_putah.py --server_ip XXXX.XXXX.XXXX.XXXX --server_port YYYY --tcp_version tahoe/reno --input input.txt")
        sys.exit(0)

    # read input.txt file
    with open(txt, "r") as file:
        message = file.read()

    # Will be userinputs[0],userinputs[1],userinputs[2],userinputs[3] respectively
    return (host,port,tcp_version,message)

def start_clientSocket(userinputs):
    # Seperate socketAddress into host,port
    host = userinputs[0]; port = userinputs[1]
    socketAddress = (host,port)

    # Make myPacket to send and outPacket to receive
    myPacket = tcpPacket(port); outPacket = tcpPacket(port)
    
    # Create client socket connection to connect with server
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as cSock:
        
        # Bind socket and save its newly created port number
        cSock.bind( (host,0) )
        cSockPort = cSock.getsockname()[1]

        # Change myPacket sport to new cSockPort and make header to send
        myPacket.setSport(cSockPort)
        myPacket.makeHeader(); myPacket.translateHeader()

        # Initiate 3-way handshake with server's 'welcoming' socket. (send SYN)
        cSock.sendto(myPacket.getHeader(), socketAddress)

        # Receive response from server's 'welcoming' socket. (get SYN/ACK)
        data,addr = cSock.recvfrom(1024)
        outPacket.copyHeader(data)

        # Prepare packet to be sent back. (send ACK)
        myPacket.makeACKpkt(outPacket); myPacket.translateHeader()

        # Get new src_port from receivers message.
        sPort = outPacket.getSport()

        # Finish 3-way handshake. (send ACK)
        cSock.sendto(myPacket.getHeader(), socketAddress)

        # Start new data socket in which all further communication will happen
        start_dataSocket(socketAddress, sPort, addr, outPacket, userinputs[2], userinputs[3])


def start_dataSocket(socketAddress, sPort, addr, myPacket, tcpVers, message):
    
    # Packet to receive data 
    outPacket = tcpPacket(0)
    
    # Reverse myPacket sport,dport,seq/acknums as they are technically the previous outPacket right now
    temp = myPacket.getSport()
    myPacket.setSport(myPacket.getDport())
    myPacket.setDport(temp)
    temp = myPacket.getSeqnum()
    myPacket.setSeqnum(myPacket.getAcknum())
    myPacket.setAcknum(temp)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dSock:
        # (IP,PORT) of receivers' new connection/data transfer socket
        receiver = (addr[0], sPort)

        # Record port of this new data socket. Set packets sPort to this now.
        dSock.bind( (socketAddress[0],0) )
        dSockPort = dSock.getsockname()[1]
        myPacket.setSport(dSockPort); myPacket.makeHeader()

        # Adjust maximum packet size in a msg to account for length of header and payload 
        totalSize = pktSize - len(myPacket.getHeader())

        # Next, split message into packets
        for i in range(0, len(message), totalSize):
            packets.append(message[i:i+totalSize])

        # Create variables to keep track of data
        msgLen = len(packets)-1
        pktsLost = 0; pktsSent = 0
        totalBits = 0
        packNum = 0
        i = 0; k = 0
        initCWND = 1; startSSTH = 16
        transmissionRound = 1; cwndArr = []; transmissionRoundArr = []
        timeoutInterval = 1
        eofCounter = 0
        
        # Boolean that checks if ssth has already halved or not
        hasDivided = 0
        dupeAck = 0

        # Acknowledgements array and has_sent array
        acknowledgements = [False for message in packets]
        packNum = 0 
        has_sent = [False for message in packets]

        # Timeout Interval Variables
        estimatedRTT = None; devRTT = None

        while True:
            try:
                # print(str(transmissionRound)+".",end=" ")
                # print(eofCounter)

                # Once all packets are sent and acknowledged. Send FIN and close connection
                if all(ele == True for ele in acknowledgements):
                    print("\nDone!")
                    break

                # Readjust timeout according to RFC and set it
                if timeoutInterval < 1:
                    timeoutInterval = 1
                dSock.settimeout(timeoutInterval)

                # SSTH and CWND adjustment area.
                # Slow Start (double cwnd)
                if initCWND < startSSTH:
                    curState = "SLOW START"
                    initCWND *= 2
                    hasDivided = 0

                # AIMD and if slow start reaches SSTH. Once threshold reached, increment by 1
                elif initCWND >= startSSTH:
                    curState = "CONGESTION AVOIDANCE"
                    if hasDivided == 0:
                        startSSTH //= 2
                        hasDivided = 1
                    initCWND += 1

                print("Acknowledged Packets: ",end="")

                # Sliding Window Sending 
                if any(ele == False for ele in acknowledgements):
                    for j in range(packNum,len(packets)):
                        
                        # Can send it if it has not been sent already
                        if has_sent[j] == False:
                            dupeAck = 0
                            # Create messages to be sent and send them
                            myPacket.setCwnd(initCWND); myPacket.makeHeader()
                            myPacket.setPayload(packets[j].encode()); myPacket.addPayload()
                            # packets[j] = adjustCWND(packets[j],initCWND) # fix this
                            startTime = time.time()
                            dSock.sendto(myPacket.getHeader(),receiver)

                            # Receive ACK
                            acknowledgement,addr = dSock.recvfrom(1024)
                            outPacket.copyHeader(acknowledgement); outPacket.setPayload(outPacket.getHeader()[17:])
                            endTime = time.time()
                            if acknowledgement not in acknowledgements:
                                acknowledgements[packNum] = True

                            # Mark as sent and increment variables. Log
                            has_sent[j] = True
                            eofCounter += 1
                            #logFormatWithCWND(messages[j],logger,INITIAL_CWND,current_state)

                        # Increment packNum 
                        if acknowledgements[packNum] == True:
                            print(packNum,end=" ")
                            myPacket.incrementNums(myPacket.getPayload(), outPacket)
                            packNum += 1
                            startTime = time.time()

                # Same as above sliding window, but for packets that could not be processed due to out of range bc of adding INITIAL_CWND
                # if packNum+initCWND > len(packets) and packNum < len(packets):
                #     for j in range(packNum,len(packets)-1):
                        
                #         # Can send it if it has not been sent already
                #         if has_sent[j] == False:
                #             dupeAck = 0
                #             # Create messages to be sent and send them
                #             myPacket.setPayload(packets[j].encode()); myPacket.addPayload()
                #             myPacket.setCwnd(initCWND); myPacket.makeHeader()
                #             # packets[j] = adjustCWND(packets[j],initCWND) # fix this
                #             startTime = time.time()
                #             print(myPacket.getPayload().decode())
                #             dSock.sendto(myPacket.getHeader(),receiver)

                #             # Receive ACK
                #             acknowledgement,addr = dSock.recvfrom(1024)
                #             endTime = time.time()
                #             if acknowledgement not in acknowledgements:
                #                 acknowledgements[packNum] = True

                #             # Mark as sent and increment variables. Log
                #             has_sent[j] = True
                #             eofCounter += 1
                #             #logFormatWithCWND(messages[j],logger,INITIAL_CWND,current_state)

                #         # Increment packNum 
                #         if acknowledgements[packNum] == True:
                #             packNum += 1
                #             startTime = time.time()

                # Same as above sliding window, but for packets that could not be processed due to out of range bc of adding INITIAL_CWND
                # if packNum+initCWND > len(packets) and packNum < len(packets):
                #     for j in range(packNum,len(packets)-1):
                        
                #         # Can send it if it has not been sent already
                #         if has_sent[j] == False:
                #             dupeAck = 0
                #             # Create messages to be sent and send them
                #             myPacket.setCwnd(initCWND); myPacket.makeHeader()
                #             myPacket.setPayload(packets[j].encode()); myPacket.addPayload()
                #             # packets[j] = adjustCWND(packets[j],initCWND) # fix this
                #             startTime = time.time()
                #             dSock.sendto(myPacket.getHeader(),receiver)

                #             # Receive ACK
                #             acknowledgement,addr = dSock.recvfrom(1024)
                #             outPacket.copyHeader(acknowledgement); outPacket.setPayload(outPacket.getHeader()[17:])
                #             endTime = time.time()
                #             if acknowledgement not in acknowledgements:
                #                 acknowledgements[packNum] = True

                #             # Mark as sent and increment variables. Log
                #             has_sent[j] = True
                #             eofCounter += 1
                #             #logFormatWithCWND(messages[j],logger,INITIAL_CWND,current_state)

                #         # Increment packNum 
                #         if acknowledgements[packNum] == True:
                #             myPacket.incrementNums(myPacket.getPayload(), outPacket)
                #             packNum += 1
                #             startTime = time.time()

                # Format next message to be sent 
                # Packets must be encoded. Then receiver can decode if they choose
                # myPacket.setPayload(packets[i].encode()); myPacket.addPayload()

                # # Send TCP packet to server
                # startTime = time.time()
                # dSock.sendto(myPacket.getHeader(),receiver)

                # # Receive acknowledgement from sender 
                # data,addr = dSock.recvfrom(1024)
                # endTime = time.time()
                # outPacket.copyHeader(data); outPacket.setPayload(outPacket.getHeader()[17:])
                
                # Check if we received correct packet. Valid == true if so
                # valid = myPacket.verifySeqAck(outPacket)
                # if valid:
                #     print("valid")
                #     myPacket.incrementNums(myPacket.getPayload(), outPacket)
                #     myPacket.delPayload()
                #     i += 1

                # # If not valid, then repeat sending process again
                # else:
                #     print("not valid")
                
                # Recalculate timeout interval
                sampleRTT = endTime - startTime
                # eRTT & devRTT are the same as sRTT at first trans. round
                if estimatedRTT == None:
                    estimatedRTT = sampleRTT
                    devRTT = sampleRTT
                estimatedRTT = (0.0875 * estimatedRTT) + (0.125 * sampleRTT)
                devRTT = (0.75 * devRTT) + (0.25 * (abs(sampleRTT-estimatedRTT)))
                timeoutInterval = estimatedRTT + (4*devRTT)
                
                # Increment Transmission Round
                transmissionRound += 1


            except socket.timeout:
                transmissionRound += 1
                if tcpVers.lower() == "tahoe":
                    startSSTH = initCWND//2
                    initCWND = 1
                elif tcpVers.lower() == "reno":
                    initCWND //= 2
                    startSSTH = initCWND
                # Delete payload before resending as the beginning of loop adds payload
                myPacket.delPayload()
                print(f"\nTimeout for packet #{packNum}, resending\n")
                
            except KeyboardInterrupt:
                myPacket.makeFINpkt(outPacket)
                print("keyboard interrupt error.")
                break

 
# 'Main' Section
start_clientSocket(getUserInput())