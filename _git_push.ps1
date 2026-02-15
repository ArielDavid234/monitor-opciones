#!/usr/bin/env pwsh
# Script to commit and push Important Companies changes

Set-Location "C:\Users\Ariel David\Desktop\Ernesto"

Write-Host "Adding files..."
git add core/projections.py app_web.py ui/components.py config/watchlists.py

Write-Host "Committing..."
git commit -m "Important Companies: fix PEG calc, remove CSV/Rec, collapsible sections"

Write-Host "Pushing to origin..."
git push origin main

Write-Host "Done!"
