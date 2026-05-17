# Login Page

This route contains the admin login screen.

## Purpose

- collect admin username and password
- call `POST /admin/login`
- store the returned token
- redirect authenticated users into the dashboard

## Related code

- UI lives in this directory
- API request logic lives in `../../lib/api.ts`
- token persistence lives in `../../lib/auth.ts`

## Running

Run the admin app from `othello-project/admin` with `npm run dev`, and make sure the backend is already running.
