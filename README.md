CS 4470 Compilers Template
==========================

Use this repository to store your work for CS 4470: Compilers.

To submit assignments, push commits to this repo.
They will be graded based on the latest commit up to the
deadline (after all granted extensions).

Setup
-----

1. Clone this repository
2. Choose a language
    * If using Python, delete `compiler.java` and `Makefile_java`, and rename `Makefile_py` to `Makefile`:
      - `rm compiler.java Makefile_java`
      - `mv Makefile_py Makefile`
    * If using Java, delete and rename vice-versa
    * If using another language (with instructor permission), create your own `Makefile` and main file and update GitHub actions accordingly. See "Choosing a Language" below for more info.
3. Inside your clone of `template/`, clone the grader and runtime repos. Add them to your gitignore. Build the runtime repo too:
   - `git clone https://github.com/utah-cs4470-sp25/grader.git`
   - `echo "grader/\nrt/" >> .gitignore`
   - `git clone https://github.com/utah-cs4470-sp25/runtime rt; cd rt; make; cd ..;`
4. For HW1, make an examples folder too. Put your HW1 work there:
   - `mkdir examples`


Choosing a Language
-------------------

This repository supports work in Java (19) or
Python (3.10). It correspondingly includes starter files
`compiler.java` and `compiler.py`. Each starter file
compiles and runs, doing nothing and returning successfully. For each
language there is also a Makefile: `Makefile_java`
and `Makefile_py`.

To choose your language, delete the starter files for the other
language and rename the remaining Makefile to be named `Makefile`. If
you want to use a language other than Java or Python, you need
special permission; contact the instructors. Keep in mind that using
another language will be more work, and you will not be able to
receive the same level of instructor support. Compilers are
complicated. Do not try to learn a new
language at the same time as you learn compilers.


Compiling your Compiler
-----------------------

A compiler is just a normal computer program. Before running it you
need to compile it. So, once you've chosen a language, compile your
compiler by running:

    make compile

This should complete without errors. If you get an error, you likely
need to install one of `javac`/`java` or `python3`
(depending on the language you chose), or to add those tools to your
system PATH. If you're having trouble with this step, please talk
to your TA or one of your instructors.

Note that if you are using Python, `make compile` will do a bit of
syntax checking but that's about it. If you are familiar with and want
to use tools like Mypy, feel free to edit your Makefile to do so.

Running your Compiler
---------------------

To test your compiler you need a test program to compile. The file
`test.jpl` is intended to be a quick scratch-pad for such tests. Run
your compiler on it with:

    make run

Of course, longer-term you'll want to save test files and run the
regularly to avoid regressions. You can change the name of the test
file like so:

    make run TEST=something.jpl

We will use this same functionality to grade your assignments.

Github Actions
--------------

Every time you push to this repository, it will compile your program
and then auto-grade the current homework assignment. The auto-grader
will roll over to the next week's assignment on Monday.

In general, you can feel free to rename files and move them around,
but the auto-grader works via Github Actions, which are configured in
the `.github` folder. Do not edit any file in that folder. You will
fail the assignment! Also do not create a folder called `grader`, that
will break the autograder.

Github actions will email you every time you push, if you fail a test.
This will be most times you push, since "failing a test" just means
you haven't finished an assignment. That will be _very_ annoying. We recommend
[turning this off][notification].

[notification]: https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/about-notifications
