# status/system – memory

<!-- path: status/system/memory -->
<!-- type: status -->

[status](../) / [system](../system.md) / memory

---

Memory object (45 fields). Returned as `status/system` → `memory`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `memtotal` | number | Total memory |
| `memfree` | number | Free memory |
| `memavailable` | number | Available memory |
| `buffers` | number | Buffers |
| `cached` | number | Cached |
| `swapcached` | number | Swap cached |
| `active` | number | Active pages |
| `inactive` | number | Inactive pages |
| `active(anon)` | number | Active anonymous |
| `inactive(anon)` | number | Inactive anonymous |
| `active(file)` | number | Active file |
| `inactive(file)` | number | Inactive file |
| `unevictable` | number | Unevictable |
| `mlocked` | number | MLocked |
| `swaptotal` | number | Swap total |
| `swapfree` | number | Swap free |
| `dirty` | number | Dirty |
| `writeback` | number | Writeback |
| `anonpages` | number | Anonymous pages |
| `mapped` | number | Mapped |
| `shmem` | number | Shared memory |
| `kreclaimable` | number | Kernel reclaimable |
| `slab` | number | Slab |
| `sreclaimable` | number | Slab reclaimable |
| `sunreclaim` | number | Slab unreclaimable |
| `kernelstack` | number | Kernel stack |
| `pagetables` | number | Page tables |
| `nfs_unstable` | number | NFS unstable |
| `bounce` | number | Bounce |
| `writebacktmp` | number | Writeback temp |
| `commitlimit` | number | Commit limit |
| `committed_as` | number | Committed as |
| `vmalloctotal` | number | vmalloc total |
| `vmallocused` | number | vmalloc used |
| `vmallocchunk` | number | vmalloc chunk |
| `percpu` | number | Per-CPU |
| `hugepages_total` | number | Huge pages total |
| `hugepages_free` | number | Huge pages free |
| `hugepages_rsvd` | number | Huge pages reserved |
| `hugepages_surp` | number | Huge pages surplus |
| `hugepagesize` | number | Huge page size |
| `hugetlb` | number | HugeTLB |
