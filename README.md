# 504:DeadlineExceeded

## Inspiration

The inspiration for this project came from procrastination and disorganization. Every student has had that moment where they look at Canvas and are completely overwhelmed and don't know where to start. This app aims to make that process a little easier and keep students focused and on track toward their goals!

## What it does

The app syncs with Canvas to track classes, assignments, due dates, and assignment descriptions. It inputs this information into a descriptive calendar where you can filter classes based on what you're currently working on. It also utilizes the Gemini API to provide key insights into each assignment such as a priority score, actionable steps, and general advice. The app also features a Gemini powered chatbot for general academic questions.

## How we built it

We built the app using a Flask framework for the backend and Vue framework for the frontend. It utilizes python as the primary backend language and HTML, CSS, and TypeScript for the frontend.

## Challenges we ran into

We ran into 2 major challenges during the project.

First being User authentication. In the beginning we wanted to use firebase for authentication since we were using gemini, it made sense to make the app fully google powered, however during implementation we could not get it to connect correctly and store users. Eventually we did a total overhaul of all firebase dependencies and switched over to Auth0 which was ultimately quicker, easier, more reliable, and more secure.

Second challenge was implementing Geminis API. The main issue that we ran into was Gemini 1.5 flash was being called, and that model has low limits and strict wording/safety policies, so it flags most text, causing the chatbot to not work. Once we switched over to 2.0 flash, most of our problems were solved. This made it reliable, faster, and more accurate.

## Accomplishments that we're proud of

We are most proud of the AI insights provided in the app. The individualized milestones will be incredibly helpful for students to avoid procrastination and leaving too much work until the last moment.

## What we learned

Prior to this project we had never used the Gemini or Canvas API. We learned how to make calls to canvas and effectively provide Gemini's API with parameters to generate insightful responses. We also learned how to cut our losses when we realized we were in too deep. Sometimes the best thing you can do is go back to the last version and try again from a different angle.

## What's next for 504:DeadlineExceeded

Currently you need to generate and input your own Canvas API key into the system for it work properly. We want to get access to a developer API for Canvas so that students will be able to log into their individual canvases from the web app itself.

### Built With:

- autho0
- canvas
- css
- flask
- gemini
- html
- python
- typescript
- vue

### Setup Instructions:
- git clone <repo_url> and cd 504-DeadlineExceeded.
- Create .env file (in "doc" folder) based on provided samples; add keys for Canvas, Auth0, Gemini, Firebase service account, etc.
- Backend: cd server, python3 -m venv .venv && source .venv/bin/activate, pip install -r requirements.txt.
- Start API: python app.py (reads .env, listens on port 5050).
- Frontend: cd ../web, npm install, create web/.env with Vite vars, npm run dev (defaults to port 5173).
- Visit http://localhost:5173; Vite proxies /api to Flask (ensure both servers running).
- Optional: run npm run build for production bundle; deploy Flask behind a real WSGI server and serve web/dist via static hosting.


