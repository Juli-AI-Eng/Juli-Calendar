# Hybrid Reclaim.ai + Nylas A2A Agent - Development Guide

## Overview

This guide outlines the development of an intelligent hybrid productivity A2A agent that combines the strengths of two complementary systems:

- **Reclaim.ai**: AI-powered task management, time blocking, and productivity optimization
- **Nylas**: Universal calendar access (Google, Outlook, iCloud, Exchange) for events and availability

The agent operates as a comprehensive "productivity expert" within Juli, intelligently routing requests to the optimal system based on user intent.

## Core Philosophy

**Intelligent Productivity Assistant**: Users interact naturally without needing to know which system handles their request. "Schedule a meeting tomorrow at 2 PM" uses Nylas, while "create a task to review the budget" uses Reclaim.ai. The AI understands intent and routes appropriately - no rigid commands, just natural conversation about productivity.

## Memories

- **Always use gpt-4.1**