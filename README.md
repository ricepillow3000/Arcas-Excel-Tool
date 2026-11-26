# Arcas

![tests](https://github.com/ricepillow3000/Arcas-Excel-Tool/actions/workflows/security.yml/badge.svg) ![Windows build](https://github.com/ricepillow3000/Arcas-Excel-Tool/actions/workflows/build-exe.yml/badge.svg)

<img src="docs/design/logo/coin-157.svg" width="80" height="80" alt="The Arcas logo: a capital A made of tiles, wine at the top to navy at the bottom, in a gold ring">

Hi there! Arcas is a free add-in for Microsoft Excel that finds the mistakes hiding in your spreadsheets.

I'm John, a student at Georgia State University in Atlanta. Checking a spreadsheet by hand always felt soul-sucking to me,
hunting through hundreds of rows for one wrong number. So I built a tool that does the hunting for you.

## Try it

**[Download Arcas.exe](https://github.com/ricepillow3000/Arcas-Excel-Tool/releases/latest/download/Arcas.exe)**

Double-click it and follow the few clicks Excel shows you. Windows may warn you because the file is new and not signed yet
([here's why](https://ricepillow3000.github.io/Arcas-Excel-Tool/code-signing.html)): click **More info**, then **Run anyway**. Need help? The website walks you through it:
https://ricepillow3000.github.io/Arcas-Excel-Tool/

## What it does

- **Finds the mistakes.** Extra zeros, typos, the same word spelled two ways, totals that don't add up, and dates that make no sense.
- **Colors the cells to check.** Orange means probably wrong. Pale yellow means worth a quick look.
- **Suggests a fix.** Click a cell to see the idea. You choose to accept it or leave it, and you can always undo.
- **Asks AI for help, if you want.** Describe the fix you need in plain words and AI writes it for you.

## Is my data safe?

Your sheet is checked on your own computer, and Arcas never deletes your data. Nothing leaves your PC unless you click
one of the AI buttons. Here is exactly what leaves and when: [What leaves your PC](PRIVACY.md).

## How I built it

I didn't type every line myself. I directed a team of AI helpers, kind of like a manager guiding a crew, and I checked
their work along the way.

Before any change goes live, over 2,000 automatic checks make sure nothing broke. Every new version is also installed
and tested on a fresh Windows computer before you can download it.

## Works with

Windows computers with the desktop version of Excel. Arcas is free for anyone, and the code is open for anyone to read
under the [MIT License](LICENSE).

## Want to dig deeper?

How it works, how to build it and how to test it: [How Arcas works](docs/DETAILS.md).
Found a problem? [Open an issue](https://github.com/ricepillow3000/Arcas-Excel-Tool/issues).

## Say hi

Have an idea, or want to build something together? Email me at john4000.nguyen@gmail.com or find me on
[LinkedIn](https://www.linkedin.com/in/john-n-7978b72b8). I'm always happy to meet new people.
