

from websockets.sync.client import connect

def main():
    uri = "ws://localhost:8081"
    with connect(uri) as websocket:
        print("Connected to EVA\n")
        
        while True:
            question = input("Ask something:\n")

            if question.lower() == "bye":
                break
            
            websocket.send(question)

            print("Eva:")
            answer = websocket.recv()
            print(f"{answer}")

if __name__ == "__main__":
    main()