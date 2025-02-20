#! /usr/bin/env python3

import scrapy, dateparser, re, datetime, icalendar, sys
from scrapy.crawler import CrawlerProcess, Crawler

def ifdef(v, fn):
    return None if v is None else fn(v)

def X(inp, sel):
    return inp.css(sel).get()

def Xstr(inp, sel):
    return X(inp, sel).strip()

def Xdate(inp, sel):
    r = X(inp, sel)
    if r is None:
        return None
    s, = ifdef(
        re.match("^[\w\s].*:(.*)$", r),
        lambda v : v.groups())
    if s is None:
        return None
    return dateparser.parse(s, settings={
        'PREFER_DATES_FROM': 'future'
    })

def Xdaterange(inp, sel):
    r = X(inp, sel)
    if r is None:
        return None
    _, sa, sz = ifdef(
        re.match("^(.*:)?\s*(.*) - (.*)$", r),
        lambda v : v.groups()
    ) or  [None, None, None]
    dz = ifdef(sa, lambda v : dateparser.parse(v, settings={
        'PREFER_DATES_FROM': 'future'
    }))
    da = ifdef(sz, lambda v : dateparser.parse(v, settings={
        'PREFER_DATES_FROM': 'future',
        'RELATIVE_BASE': dz if dz is not None else datetime.datetime.now()
    }))
    return [da, dz]

class IACREventsScraper(scrapy.Spider):
    name = "iacr-events"
    start_urls = ['https://iacr.org/events/']

    def parse(self, res):
        for ev in res.css('.event-list > *'):
            rawTitle = Xstr(ev, '.event-title *::text').strip()
            title, _, short = ifdef(
                re.match("^(.*)\s*(\(([^)(]*)\))?", rawTitle),
                lambda v : v.groups()) or [None, None, None]
            yield {
                'title': title,
                'short': short,
                'url': X(ev, '.event-title a::attr(href)'),
                'location': Xstr(ev, '.event-location *::text'),
                'date': Xdaterange(ev, '.event-dates *::text'),
                'deadline': Xdate(ev, '.event-submit *::text'),
                'notification-date': Xdate(ev, '.event-notification *::text')
            }

def crawl():
    r = []
    def collect_items(item, response, spider):
        r.append(item)

    c = Crawler(IACREventsScraper)
    c.signals.connect(collect_items, scrapy.signals.item_scraped)

    cp = CrawlerProcess()
    cp.crawl(c)
    cp.start()

    return r

# Sixty lines of boilerplate later…
def main():
    cal = icalendar.Calendar()
    cal.add('prodid', '-//IACR Events Calender//mxm.dk//')
    cal.add('version', '2.0')

    for ev in crawl():
        iev = icalendar.Event()
        def P(k, v):
            if v is not None:
                iev.add(k, v)

        desc = []
        def D(k, v):
            if v is not None:
                desc.append(f'{k}: {v}')

        if ev['short'] is not None:
            P('summary', ev['short'])
            desc.append(ev['title'])
            desc.append('')
        else:
            P('summary', ev['title'])

        start, end = ev['date']
        start = start or end
        end = end or start
        if start is None or end is None:
            print("[WARNING] EVENT WITHOUT TIME; IGNORING IT.", ev['short'], file=sys.stderr)

        P('url', ev['url'])
        P('location', ev['location'])
        P('dtstart', start)
        P('dtstamp', start)
        P('dtend', end)

        D('Submission-Deadline', ev['deadline'])
        D('Notification-Date', ev['notification-date'])

        P('description', "\n".join(desc).strip())

        cal.add_component(iev)

    sys.stdout.write(str(cal.to_ical(), 'utf-8'))

main()
