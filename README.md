# shooter

## Description

A program to send and receive messages based on ZMQ and Protobuf (see orwell-int/messages).


## Requirements

Python 2.7
zmq
protobuf (v2)
make

## Usage

Get and install dependencies and create virtual environment.
```
make develop
```

Test with simple scenario that things work.
```
make start
```

Test with unittests that things work.
```
make test
```

To launch a scenario of your own you need to activate the virtual environment and call it directly.
The following example works as standalone.
```
source env/bin/activate
python orwell/shooter/main.py Standalone.yml -d 1
```

## Scenario files

The format can mostly be deduced from the examples. Each scenario file is a YAML file.
The main three sections are
* messages: you may describe you messages in advance here
* sockets: you may put the different sockets needed for communications (two for each thread: in/out)
* threads: each thread can be seen as a small program that will send and receive messages as expect and perform some more actions

Actions available:
* In: receive a message (messages of the wrong type are discarded)
* Out: send a message
* Equal: assert values are identical
* Absent: asssert that a value is absent for a collection
* Sleep: sleep for some time in seconds
* UserInput: wait for user input
