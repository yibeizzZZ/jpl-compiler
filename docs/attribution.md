# Attribution and provenance

This repository originated as work for **CS 4470: Compilers** and contains both
course-derived scaffolding and compiler implementation developed in the
repository. Its presentation as a portfolio project does not imply sole
authorship of every file or authorship of course-provided material.

## Course-provided foundation

The original README identifies the project as the **CS 4470 Compilers Template**
and explicitly describes `compiler.py` and the Makefile as starter files.
In the early template-era commit `e371782`, `compiler.py` contains only a Python
entry-point stub; the Makefile provides basic compile/run/clean targets.
The original workflow and submission instructions also belong to the course
infrastructure. The current entry point and build configuration evolved from
that foundation, and are not presented as wholly original scaffolding.

The original material remains accessible without restoring grading commands:

```sh
git show e371782:README.md
git show e371782:compiler.py
git show e371782:Makefile
```

## Compiler implementation and contributors

The lexer, parser/AST, semantic and type checks, C emitter, x86-64 emitter, and
stack/calling-convention helpers are the compiler implementation developed in
this repository. The [implementation audit](implementation.md) describes their
actual mechanisms and limitations; it does not assign individual authorship
to each mechanism or claim that course language/runtime design was original.

Git history records contributions under the names `yibeizzZZ`, `yibeizzZ`, and
`Kai001020`. Those existing records are preserved. Importing a starter file in a
commit does not establish original authorship of the imported material, and the
portfolio documentation does not attribute a collaborator's work solely to
the repository maintainer.

## Runtime and example assets

The JPL runtime was supplied separately through the course. Its source and
header are not included in this checkout. References such as `rt/runtime.h`,
`_jpl_alloc`, `_show`, and `_read_image` describe an external dependency; they
do not represent a runtime implementation authored in this repository.

The example programs and PNGs are preserved as existing project materials.
Some were already present in the early template-era import, and their individual
original authorship is not established by this audit. They are not presented
as newly created assets or proof of output from the current compiler.

## Notices and history

No top-level license file or explicit copyright/license notice was present in
the inspected baseline (`16472a0`). No such notice was removed by this cleanup,
and no new license or ownership claim has been assigned to third-party material.

Cleanup affects the working tree only. Git history, original authorship records,
and historical course material have not been rewritten.
