#imports yarn from purstraction
from pawcket import yarn, pawprint

yarnball = yarn(True)

@yarnball.thread("/")
def index():
    pawprint["test123"] = "hello"
    return yarnball.spin_yarn("meow.html")

@yarnball.thread("/test")
def test():
    return pawprint["test123"]

if __name__ == "__main__":
    yarnball.roll()