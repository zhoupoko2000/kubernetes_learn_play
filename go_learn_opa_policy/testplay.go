package main

import (
	"fmt"
	"runtime"
)

func main(){
	fmt.Println("Hello From " + runtime.GOOS)
}