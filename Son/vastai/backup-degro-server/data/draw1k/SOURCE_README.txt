README
======

This is a public release of the dataset corresponding paper "Annotating Derivations: A New Evaluation Strategy and Dataset for Algebra Word Problems". It consists of over 2000 algebra word problems.
Each word problem is annotated with the full derivation (template + alignments) of the relevant equations from the word problem. 
Please refer the paper https://aka.ms/derivationpaper for details.

Contents
(1) 1000 new training/testing data with diverse templates and narratives crawled from algebra.com. (DRAW dataset in the paper) 
(2) Word problems from http://groups.csail.mit.edu/rbg/code/wordprobs/ annotated using our proposed schema. (Alg-514 in the paper)
(3) Word problems from linear-T2 subset from http://research.microsoft.com/en-us/projects/dolphin/ annotated using our proposed schema. (Dolphin-L in the paper)
Templates annotated in all the above datasets were globally reconciled. The cross validation splits and train-test splits used in the papers are also provided (Thanks to the respective authors for sharing the splits).

We will use the following example to explain the fields:

# the tokenized version of the word problem
"sQuestion": "In a chemistry class , 5 liters of 4 % silver solution must be mixed with a 10 % solution to get a 6 % solution . How many liters of the 10 % solution are needed ?", 
# the equation systme
"lEquations": [".01*4*(5)+.01*10*x=.01*6*(5+x)"], 
# the solution
"lSolutions": [2.5], 
# the template; a, b, ... represents the coefficients while m,n, ... represents the variables
"Template": [ "a * m - b * m = b * c - c * d"], 
# problem id
"iIndex": 300319, 
# the alignments between the coefficients and textual numbers
"Alignment": [
   {
    "coeff": "d", 
    "SentenceId": 0, 
    "Value": 4.0, 
    "TokenId": 8
   }, 
   {
    "coeff": "c", 
    "SentenceId": 0, 
    "Value": 5.0, 
    "TokenId": 5
   }, 
   {
    "coeff": "a", 
    "SentenceId": 0, 
    "Value": 10.0, 
    "TokenId": 17
   }, 
   {
    "coeff": "b", 
    "SentenceId": 0, 
    "Value": 6.0, 
    "TokenId": 23
   }
  ], 
 # the alignments sometimes are not unique; this shows that the textual number on the 17-th token of the 0-th setnence is the same as the 5-th token of the 1-st sentence. Their values are both 10s.
 "Equiv": [[[0, 17, 10], [1, 5, 10]]]
  
 
If you found the dataset useful, please support our work by citing our paper. Please email the authors if you find any problems.

p.s. When conducting the experiments on Dolphin-L, note that the training data contains all of the examples which are not in the test split. There are some examples belong to the development set, and they do not belong to any test split in any fold.

