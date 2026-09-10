main.pdf: main.tex refs.bib vendor/aamas.cls vendor/ACM-Reference-Format.bst
	TEXINPUTS=vendor//: BSTINPUTS=vendor//: latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

clean:
	latexmk -C main.tex
