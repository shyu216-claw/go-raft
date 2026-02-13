package main

import (
	"context"
	"cuhk/asgn/raft"
	"fmt"
	"google.golang.org/grpc"
	"log"
	"net"
	"os"
	"strconv"
	"strings"
	"time"
)

func main() {
	ports := os.Args[2]
	myport, _ := strconv.Atoi(os.Args[1])
	nodeID, _ := strconv.Atoi(os.Args[3])
	heartBeatInterval, _ := strconv.Atoi(os.Args[4])
	electionTimeout, _ := strconv.Atoi(os.Args[5])

	portStrings := strings.Split(ports, ",")

	// A map where
	// 		the key is the node id
	//		the value is the {hostname:port}
	nodeidPortMap := make(map[int]int)
	for i, portStr := range portStrings {
		port, _ := strconv.Atoi(portStr)
		nodeidPortMap[i] = port
	}

	// Create and start the Raft Node.
	_, err := NewRaftNode(myport, nodeidPortMap,
		nodeID, heartBeatInterval, electionTimeout)

	if err != nil {
		log.Fatalln("Failed to create raft node:", err)
	}

	// Run the raft node forever.
	select {}
}

type raftNode struct {
	log []*raft.LogEntry
	// TODO: Implement this!
	// log is a slice

	// self info
	serverState raft.Role
	currentTerm int32
	votedFor int32
	
	// two types of timer
	electionTimeout int32
	heartBeatInterval int32
	
	// use one channel to reset the timer
	resetChan chan bool

	// commit
	// index of latest committed index
	commitIndex int32
	commitChan chan bool

	// leader's concern
	// map looks better
	nextIndex map[int32]int32
	matchIndex map[int32]int32

	// a lock
	chanLock chan bool

	// 
	kvstore map[string]int32
	// Put: key=3, value=2 ==> kvstore[3]=2
	// Delete...
}

// Desc:
// NewRaftNode creates a new RaftNode. This function should return only when
// all nodes have joined the ring, and should return a non-nil error if this node
// could not be started in spite of dialing any other nodes.
//
// Params:
// myport: the port of this new node. We use tcp in this project.
//			   	Note: Please listen to this port rather than nodeidPortMap[nodeId]
// nodeidPortMap: a map from all node IDs to their ports.
// nodeId: the id of this node
// heartBeatInterval: the Heart Beat Interval when this node becomes leader. In millisecond.
// electionTimeout: The election timeout for this node. In millisecond.
func NewRaftNode(myport int, nodeidPortMap map[int]int, nodeId, heartBeatInterval,
	electionTimeout int) (raft.RaftNodeServer, error) {
	// TODO: Implement this!

	//remove myself in the hostmap
	delete(nodeidPortMap, nodeId)

	//a map for {node id, gRPCClient}
	hostConnectionMap := make(map[int32]raft.RaftNodeClient)

	rn := raftNode{		
		// log: nil,
		// log is a slice
		log: make([]*raft.LogEntry,0),
	
		// self info
		serverState: raft.Role_Follower,
		currentTerm: 0,
		// votedFor: nil,
		
		// two types of timer
		heartBeatInterval: int32(heartBeatInterval),
		electionTimeout: int32(electionTimeout),
		
		// use one channel to reset the timer
		resetChan: make(chan bool, 1),
	
		// commit
		commitIndex: 0,
		commitChan: make(chan bool, 1),
	
		// leader's concern
		nextIndex: make(map[int32]int32),
		matchIndex: make(map[int32]int32),
	
		// a lock
		chanLock: make(chan bool, 1),

		// key value store
		kvstore: make(map[string]int32),
		// Put: key=3, value=2 ==> kvstore[3]=2
		// Delete...
	}

	l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", myport))

	if err != nil {
		log.Println("Fail to listen port", err)
		os.Exit(1)
	}

	s := grpc.NewServer()
	raft.RegisterRaftNodeServer(s, &rn)

	log.Printf("Start listening to port: %d", myport)
	go s.Serve(l)

	//Try to connect nodes
	for tmpHostId, hostPorts := range nodeidPortMap {
		hostId := int32(tmpHostId)
		numTry := 0
		for {
			numTry++

			conn, err := grpc.Dial(fmt.Sprintf("127.0.0.1:%d", hostPorts), grpc.WithInsecure(), grpc.WithBlock())
			//defer conn.Close()
			client := raft.NewRaftNodeClient(conn)
			if err != nil {
				log.Println("Fail to connect other nodes. ", err)
				time.Sleep(1 * time.Second)
			} else {
				hostConnectionMap[hostId] = client
				break
			}
		}
	}
	log.Printf("Successfully connect all nodes")

	//TODO: kick off leader election here !
	rn.log = append(rn.log, &raft.LogEntry{
		Term:0,
		Op:raft.Operation_Put,
		Key:"head",
		Value:0,
	})

	ctx := context.Background()
	go func(){
		for {
		switch rn.serverState{
			case raft.Role_Follower:
				//
				select{
				// timer for election
				case <- time.After(time.Duration(rn.electionTimeout)*time.Millisecond):
						rn.serverState=raft.Role_Candidate
				case <- rn.resetChan:
						// could do nothing here, just empty
				}
			case raft.Role_Candidate:
				//
				rn.currentTerm++
				// vote for myself
				rn.votedFor = int32(nodeId)
				voterNum := 0
				// invoke the requestvote rpc of the other raft vote
				// myself not in hostConnectionMap
				for hostId, client := range hostConnectionMap {
					go func(hostId int32, client raft.RaftNodeClient){
						r, err := client.RequestVote(
							ctx,
							&raft.RequestVoteArgs{
								From: int32(nodeId),
								To: int32(hostId),
								Term: rn.currentTerm,
								CandidateId: int32(nodeId),
								LastLogIndex: int32(len(rn.log)-1),
								LastLogTerm: rn.log[len(rn.log)-1].Term,
							},
						)
						if err == nil && r.VoteGranted == true && r.Term == rn.currentTerm && rn.serverState == raft.Role_Candidate {

							// add a lock
							// either channel or mutex lock
							// sync.Mutex.Lock()
							// sync.Mutex.Unlock()
							rn.chanLock <- true

							voterNum++

							if voterNum >= len(hostConnectionMap)/2 && rn.serverState == raft.Role_Candidate {
								rn.serverState=raft.Role_Leader

								for tempId,_ := range hostConnectionMap {
									rn.nextIndex[tempId] = int32(len(rn.log))
									rn.matchIndex[tempId] = 0
								}

								rn.resetChan <- true
							}
							
							<-rn.chanLock
						}

						if err == nil && r.VoteGranted == false {
							// log.Printf("false vote reply")
							if r.Term > rn.currentTerm {
								// I dont know my votedFor now...
								rn.serverState = raft.Role_Follower
								rn.resetChan <- true
							} 
						}
					}(hostId, client)
				}
				// what if not get enough vote eventually?

				select {
				case <- time.After(time.Duration(rn.electionTimeout)*time.Millisecond):
					// empty
				case <- rn.resetChan:
					// empty
				}
			case raft.Role_Leader:
				//
				
				// check the matchIndex
				// find N, majority of the matchIndex[i] >= N, commit those logs
				// update the rn.commitIndex
				// ignore in my impl

				for hostId, client := range hostConnectionMap {
					// some follower may miss multiple logs
					sendLog := make([]*raft.LogEntry,0)
					for i := rn.nextIndex[hostId]; i<int32(len(rn.log));i++ {
						sendLog = append(sendLog, rn.log[i])
					}
					
					go func(hostId int32, client raft.RaftNodeClient){
						r, err := client.AppendEntries(
							ctx,
							&raft.AppendEntriesArgs {
								From: int32(nodeId),
								To: int32(hostId),
								Term: rn.currentTerm,
								LeaderId: int32(nodeId),
								PrevLogIndex: rn.nextIndex[hostId]-1,
								PrevLogTerm: rn.log[rn.nextIndex[hostId]-1].Term,
								Entries: sendLog,
								LeaderCommit: rn.commitIndex,
							},
						)
						// log.Printf("Hear from",hostId,r)
						if err == nil && r.Success == true {
						
							// check if the follower has received the logs
							// if the majority has received, commit it
							// log.Printf("commitindex",rn.commitIndex)
							// log.Printf("matchindex",rn.matchIndex)

							// add a lock
							rn.chanLock <- true
							
							rn.matchIndex[hostId]=r.MatchIndex
							commitNum:=0

							for _,v := range rn.matchIndex{
								if v > rn.commitIndex{
									commitNum++
								}
							}
							
							// log.Printf("commitNum ",commitNum)
							// log.Printf("total",len(hostConnectionMap))
							if commitNum >= len(hostConnectionMap)/2{
								rn.commitIndex++
								rn.commitChan <- true
							}
							
							rn.nextIndex[hostId]=rn.nextIndex[hostId] + int32(len(sendLog))
							
							<-rn.chanLock
							
						}else if err == nil && r.Success == false {
							// log.Printf("false append reply")
							rn.chanLock<-true
							rn.nextIndex[hostId]--
							if r.Term > rn.currentTerm {
								// I am not leader now...
								rn.serverState = raft.Role_Follower
								rn.resetChan <- true
							}
							<-rn.chanLock
						}
					}(hostId, client)
				}

				select{
				case<- time.After(time.Duration(rn.heartBeatInterval)*time.Millisecond):
					// empty
				case<-rn.resetChan:
					// empty
				}
			}
		}
	}()

	return &rn, nil
}

// Desc:
// Propose initializes proposing a new operation, and replies with the
// result of committing this operation. Propose should not return until
// this operation has been committed, or this node is not leader now.
//
// If the we put a new <k, v> pair or deleted an existing <k, v> pair
// successfully, it should return OK; If it tries to delete an non-existing
// key, a KeyNotFound should be returned; If this node is not leader now,
// it should return WrongNode as well as the currentLeader id.
//
// Params:
// args: the operation to propose
// reply: as specified in Desc
func (rn *raftNode) Propose(ctx context.Context, args *raft.ProposeArgs) (*raft.ProposeReply, error) {
	// TODO: Implement this!
	log.Printf("Receive propose from client")
	var ret raft.ProposeReply

	// rest timer 
	// invoke AppendEntries RPC 
	if rn.serverState == raft.Role_Leader{

		ret.CurrentLeader = rn.votedFor // nodeID
		ret.Status = raft.Status_OK

		// append the log to local log
		rn.chanLock <- true
		rn.log = append(rn.log, &raft.LogEntry{
			Term: rn.currentTerm,
			Op: args.Op,
			Key: args.Key,
			Value: args.V,
		})
		<- rn.chanLock
		// log.Printf("Propose waiting")

		<- rn.commitChan

		rn.chanLock<-true
		if args.Op == raft.Operation_Put {
			rn.kvstore[args.Key]=args.V
		}else if args.Op == raft.Operation_Delete{
			// check if the key exists in kvstore
			// if yes, delete, otherwise return key not found
			// res.Status = raft.Status_KeyNotFound
			if _,ok:=rn.kvstore[args.Key];ok{
				delete(rn.kvstore,args.Key)
			}else{
				ret.Status = raft.Status_KeyNotFound
			}
		}
		<-rn.chanLock

	}else{
		ret.CurrentLeader=rn.votedFor
		// only the leader can accept new operations
		ret.Status=raft.Status_WrongNode
	}
	// log.Printf("Done a propose")

	return &ret, nil
}

// Desc:GetValue
// GetValue looks up the value for a key, and replies with the value or with
// the Status KeyNotFound.
//
// Params:
// args: the key to check
// reply: the value and status for this lookup of the given key
func (rn *raftNode) GetValue(ctx context.Context, args *raft.GetValueArgs) (*raft.GetValueReply, error) {
	// TODO: Implement this!
	var ret raft.GetValueReply
	// add a lock
	rn.chanLock <- true
	if val, ok := rn.kvstore[args.Key]; ok{
		ret.V = val
		ret.Status = raft.Status_KeyFound
	}else{
		ret.V = -1
		ret.Status = raft.Status_KeyNotFound
	}
	<- rn.chanLock
	return &ret, nil
}

// Desc:
// Receive a RecvRequestVote message from another Raft Node. Check the paper for more details.
//
// Params:
// args: the RequestVote Message, you must include From(src node id) and To(dst node id) when
// you call this API
// reply: the RequestVote Reply Message
func (rn *raftNode) RequestVote(ctx context.Context, args *raft.RequestVoteArgs) (*raft.RequestVoteReply, error) {
	// TODO: Implement this!
	var reply raft.RequestVoteReply

	reply.From = args.To
	reply.To = args.From

	if args.Term > rn.currentTerm{
		rn.votedFor = args.CandidateId
		rn.currentTerm = args.Term
		if rn.serverState != raft.Role_Follower {
			rn.serverState = raft.Role_Follower
			// tell main function i have changed the role
			// use a channel
			rn.resetChan<- true
		}
	}

	reply.Term = rn.currentTerm

	if args.Term == rn.currentTerm && args.CandidateId == rn.votedFor && args.LastLogIndex >= int32(len(rn.log))-1 && args.LastLogTerm >= rn.log[len(rn.log)-1].Term {
		reply.VoteGranted = true
		rn.resetChan<- true
	}else{
		reply.VoteGranted = false
	}

	return &reply, nil
}

// Desc:
// Receive a RecvAppendEntries message from another Raft Node. Check the paper for more details.
//
// Params:
// args: the AppendEntries Message, you must include From(src node id) and To(dst node id) when
// you call this API
// reply: the AppendEntries Reply Message
func (rn *raftNode) AppendEntries(ctx context.Context, args *raft.AppendEntriesArgs) (*raft.AppendEntriesReply, error) {
	// TODO: Implement this
	var reply raft.AppendEntriesReply

	reply.From=args.To
	reply.To =args.From
	reply.Success = true
	reply.MatchIndex = 0
	
	if args.Term >= rn.currentTerm{
		rn.votedFor = args.From
		rn.currentTerm =args.Term
		// change our role to follower
		rn.serverState = raft.Role_Follower
		// if you are leader, do you need to reset the timer?
		// if I am a out of date leader, but doing another append now, what should I do...
		// the uncommitted logs doesn't matter any more, if the majority have it, new leader will take care of it
		rn.resetChan <- true
	}
	reply.Term = rn.currentTerm
	
	// old leader
	if args.Term < rn.currentTerm{
		reply.Success = false
	}

	if args.PrevLogIndex < int32(len(rn.log)) && args.PrevLogTerm == rn.log[args.PrevLogIndex].Term {	
		// update local log if success
		rn.log = rn.log[:args.PrevLogIndex+1]
		rn.log = append(rn.log, args.Entries...)

		// log.Printf("LOG",rn.log)
		reply.MatchIndex = int32(len(rn.log))-1

		// apply the commited log by comparing commitIndex and LeaderCommit
		if args.LeaderCommit > rn.commitIndex{
			// apply the committed logs
			rn.chanLock<-true
			for i := rn.commitIndex+1;i<=args.LeaderCommit;i++{
				if rn.log[i].Op == raft.Operation_Put {
					rn.kvstore[rn.log[i].Key]=rn.log[i].Value
				}else if rn.log[i].Op == raft.Operation_Delete{
					if _,ok:=rn.kvstore[rn.log[i].Key];ok{
						delete(rn.kvstore,rn.log[i].Key)
					}
				}
			}
			<-rn.chanLock
			rn.commitIndex=args.LeaderCommit
		}
	} else {
		reply.Success = false
	}

	return &reply, nil
}

// Desc:
// Set electionTimeOut as args.Timeout milliseconds.
// You also need to stop current ticker and reset it to fire every args.Timeout milliseconds.
//
// Params:
// args: the heartbeat duration
// reply: no use
func (rn *raftNode) SetElectionTimeout(ctx context.Context, args *raft.SetElectionTimeoutArgs) (*raft.SetElectionTimeoutReply, error) {
	// TODO: Implement this!
	var reply raft.SetElectionTimeoutReply
	rn.electionTimeout = args.Timeout
	rn.resetChan <- true
	return &reply, nil
}

// Desc:
// Set heartBeatInterval as args.Interval milliseconds.
// You also need to stop current ticker and reset it to fire every args.Interval milliseconds.
//
// Params:
// args: the heartbeat duration
// reply: no use
func (rn *raftNode) SetHeartBeatInterval(ctx context.Context, args *raft.SetHeartBeatIntervalArgs) (*raft.SetHeartBeatIntervalReply, error) {
	// TODO: Implement this!
	var reply raft.SetHeartBeatIntervalReply
	rn.heartBeatInterval = args.Interval
	rn.resetChan <- true
	return &reply, nil
}

//NO NEED TO TOUCH THIS FUNCTION
func (rn *raftNode) CheckEvents(context.Context, *raft.CheckEventsArgs) (*raft.CheckEventsReply, error) {
	return nil, nil
}
