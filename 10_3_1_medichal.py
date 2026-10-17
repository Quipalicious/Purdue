"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     10.3.1
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

""" Write any import statements here (and delete this line)."""


def main():
    user_input = input("Enter items separated by commas (no spaces): ")
    items = user_input.split(",")
    errors = 0

    for i in range(len(items)):
        if items[i] == "normal":
            print("Moving item to standard bin")
        elif items[i] == "fragile":
            print("Handling fragile item with care")
        elif items[i] == "heavy":
            print("Activating lift assist for heavy item")
        elif items[i] == "error":
            print("ALERT: Item error detected - robot needs help!")
            errors += 1
        else:
            print("Sending item to inspection")

        if errors >= 3:
            print("ALERT: Too many errors - sending robot to inspection")
            break

        





if __name__ == "__main__":
    main()
