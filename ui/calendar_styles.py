"""
Estilos CSS para el calendario financiero
"""

CALENDAR_CSS = """
<style>
html { scroll-behavior: smooth; }
.calendar-header {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
    margin-bottom: 0;
}
.calendar-day-header {
    background: #1e3a5f;
    color: #e2e8f0;
    padding: 10px 4px;
    text-align: center;
    font-weight: 700;
    border-radius: 6px 6px 0 0;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
}
.calendar-cell {
    min-height: 85px;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 5px;
    background: #1a1a2e;
    position: relative;
    transition: background 0.2s, transform 0.15s;
}
.calendar-cell-link {
    text-decoration: none;
    color: inherit;
    display: block;
    cursor: pointer;
}
.calendar-cell-link:hover .calendar-cell {
    background: #2a2a4e;
    transform: scale(1.02);
    border-color: #4a90d9;
}
.calendar-cell-empty {
    background: #111827;
    border-color: #1f2937;
}
.calendar-day-number {
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 3px;
    color: #e2e8f0;
}
.calendar-event {
    background: #2563eb;
    color: #ffffff;
    border-radius: 4px;
    padding: 2px 5px;
    margin: 2px 0;
    font-size: 0.7rem;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 500;
}
.event-fed { background: #b91c1c; color: #ffffff; }
.event-earnings { background: #047857; color: #ffffff; }
.event-ceo { background: #b45309; color: #ffffff; }
.event-inversor { background: #4338ca; color: #ffffff; }
.day-detail-section {
    background: #1a1a2e;
    border: 1px solid #2d3748;
    border-radius: 10px;
    margin: 8px 0;
    overflow: hidden;
}
.day-detail-section summary {
    font-size: 1.05rem;
    font-weight: 700;
    color: #e2e8f0;
    padding: 14px 16px;
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
    user-select: none;
    transition: background 0.2s;
}
.day-detail-section summary:hover {
    background: rgba(59, 130, 246, 0.1);
}
.day-detail-section summary::-webkit-details-marker { display: none; }
.day-detail-section summary::before {
    content: '▶';
    display: inline-block;
    transition: transform 0.2s;
    font-size: 0.8rem;
}
.day-detail-section[open] summary::before {
    transform: rotate(90deg);
}
.day-detail-content {
    padding: 4px 16px 16px 16px;
}
.day-detail-event {
    background: rgba(59, 130, 246, 0.1);
    border-left: 4px solid #3b82f6;
    padding: 12px;
    margin: 8px 0;
    border-radius: 0 8px 8px 0;
}
.day-detail-event-title {
    font-weight: 600;
    color: #60a5fa;
    margin-bottom: 4px;
    font-size: 0.95rem;
}
.day-detail-event-desc {
    color: #94a3b8;
    font-size: 0.9rem;
    margin-bottom: 6px;
}
.day-detail-event-meta {
    font-size: 0.8rem;
    color: #64748b;
}
.calendar-info {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 16px;
}
</style>
"""