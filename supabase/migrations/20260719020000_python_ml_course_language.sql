-- Add python-ml as a third course-level language alongside python/cpp: a GPU-capable
-- ML/DL sandbox profile (numpy/pandas/scipy/scikit-learn/matplotlib/seaborn/torch/
-- torchvision/pytest) distinct from python-basic's from-scratch-numpy track. No data
-- migration needed -- existing 'python'/'cpp' rows are untouched, this only widens what
-- new/updated rows may be.

alter table public.courses
  drop constraint if exists courses_language_check;

alter table public.courses
  add constraint courses_language_check check (language in ('python', 'python-ml', 'cpp'));
