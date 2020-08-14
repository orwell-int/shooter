env/bin/activate:
	python3 -m venv env
	. env/bin/activate && pip install -U pip wheel && pip install -r requirements.txt
	cd messages && python3 ./generate.py ../

develop: env/bin/activate
	git submodule update --init

test: develop
	. env/bin/activate && nosetests

coverage: env/bin/activate
	. env/bin/activate && nosetests --with-coverage --cover-erase --cover-branches --cover-package=orwell

clean: env/bin/activate
	. env/bin/activate && coverage erase

start: env/bin/activate
	. env/bin/activate && python3 ./orwell/shooter/main.py Standalone.yml -d 1
