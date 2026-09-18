# Scheduling checkpoint

During the first wave, response latency varied substantially across workers. Some
workers had finished their 74–76 requests while other workers had completed only
30–35 requests after about 19 minutes, with recent requests taking 46–77 seconds.

The first-wave runner and its specifically verified child processes were stopped.
All stored responses were preserved: 1,769 valid thinking-on responses and 1,877
valid thinking-off responses. In-flight requests at the stop point were interrupted;
they were not selected or discarded according to correctness.

The same frozen dataset, model, prompt, temperature, scoring policy, account pool
and request timeout were resumed with 32 shards instead of eight, retaining the
maximum concurrency of 64 and scheduling only cases lacking a valid stored response.
The resumed pass is counted as wave two within the four-wave limit.

This scheduling change is operational, not an additional model/config condition.
Elapsed latency is therefore descriptive rather than a controlled speed benchmark.
