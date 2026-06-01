# Pre-amble ---------------------------------------------------------------

library(tidyverse)
library(broom)

# Read in data ------------------------------------------------------------

## ++ meetings
message("Reading in meeting data")
meetings_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/meetings.rds" ## FASRC
# meetings_fpath <- "meetings.rds" ## local

if (!"dat" %in% ls()) {
  dat <- readRDS(meetings_fpath) ## ~2 minutes
  print(paste0("n = ", nrow(dat)))
  print(table(`Meeting Years:`=substr(dat$meeting_date, 1, 4)))
}

dat.ex <- dat %>%
  filter(grepl("climate change", caption_text)) %>%
  mutate(caption_text = stringr::str_extract(caption_text, ".{50}climate change.{50}")) %>%
  mutate(caption_text_clean = stringr::str_extract(caption_text_clean, ".{50}climate change.{50}"))
dat.ex %>%
  filter(!is.na(place_Pres_dem2pv)) %>%
  sample_n(1) %>%
  glimpse(.)
dat %>%
  filter(vid_id =="LSN5QBkDtEs")

## ++ geography
places_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/external/geography_ST_FIPS.csv" ## FASRC
# places_fpath <- "geography_ST_FIPS.csv"
places <- read_csv(places_fpath)

## ++ demographics
acs_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/external/acs_2018.rds"
# acs_fpath <- "acs_2018.rds" ## FASRC
acs <- readRDS(acs_fpath)

# Supplementary analyses --------------------------------------------------

## ++ number of videos over time ------------------------------------------

n.vids <- dat %>%
  mutate(meeting_date = as.numeric(format(meeting_date, "%Y"))) %>%
  rowwise() %>%  
  group_by(meeting_date) %>%
  summarise(n=n(), .groups="drop")

n.places <- dat %>%
  mutate(meeting_date = as.numeric(format(meeting_date, "%Y"))) %>%
  rowwise() %>%
  group_by(meeting_date) %>%
  summarise(n=length(unique(st_fips)), .groups="drop")

n.govts <- dat %>%
  mutate(meeting_date = as.numeric(format(meeting_date, "%Y"))) %>%
  rowwise() %>%
  mutate(unique_govt = paste(st_fips, place_govt)) %>%  
  group_by(meeting_date) %>%
  summarise(n=length(unique(unique_govt)), .groups="drop")

bind_rows(bind_cols(n.vids, type="Number of Meeting Videos"),
          bind_cols(n.places, type="Number of Places"),
          bind_cols(n.govts, type="Number of Governments")) %>%
  mutate(type = as_factor(type)) %>%
  ggplot(aes(x=meeting_date, y=n)) + 
  scale_y_binned(labels = scales::comma_format(1)) +
  # scale_x_date(date_labels = "%Y", date_breaks = "12 months", date_minor_breaks = "6 months") +
  xlab("Year") + ylab("") +
  facet_grid(type ~ ., scales = "free_y") +
  geom_point(alpha = 0.5, size=3) +
  geom_line() +
  theme_bw() + 
  theme(legend.position = "bottom",
        strip.text = element_text(face = "bold"),
        strip.background = element_rect(fill = "#EEE5E5"))
ggsave("out/over_time.pdf", width = 7, height = 7)

## ++ mistranscription rates ----------------------------------------------

### by region
unique(places$STNAME[places$state_region == "North Central"])
dat %>%
  left_join(places %>% 
              select(st_fips, state_region)) %>%
  filter(!is.na(state_region)) %>%
  group_by(state_region) %>%
  summarise(n_vids = n(),
            pct_captions = mean(!is.na(caption_text)), 
            .groups="drop")

### by division
dat %>%
  left_join(places %>% 
              select(st_fips, state_division)) %>%
  filter(!is.na(state_division)) %>%
  group_by(state_division) %>%
  summarise(n_vids = n(),
            pct_captions = mean(!is.na(caption_text)), 
            .groups="drop")

d.pct_captions <- dat %>%
  left_join(places %>% 
              select(st_fips, state_region, state_division)) %>%
  filter(!is.na(state_division)) %>%
  group_by(st_fips) %>%
  summarise(across(starts_with("channel_is"), ~sum(.x)),
            across(starts_with("acs_"), ~first(.x)),
            state_region = first(state_region),
            state_division = first(state_division),
            n_channels = length(unique(channel_id)),
            n_vids = length(unique(vid_id)),
            n_captions = sum(!is.na(caption_text)),
            pct_captions = mean(!is.na(caption_text)),
            .groups = "drop")
summary(lm(pct_captions ~ log(acs_2018_pop+1) + log(acs_2018_white+1) + log(acs_2018_black+1) + state_region, 
           data = d.pct_captions))
summary(lm(log(n_captions+1) ~ log(n_vids+1) + log(acs_2018_pop+1) + log(acs_2018_white+1) + log(acs_2018_black+1) + state_region, 
           data = d.pct_captions))
summary(lm(log(n_captions+1) ~ log(n_vids+1) + log(acs_2018_pop+1) + log(acs_2018_white+1) + log(acs_2018_black+1) + state_division, 
           data = d.pct_captions))

lm(log(n_captions+1) ~ log(n_vids+1) + log(acs_2018_pop+1) + log(acs_2018_white+1) + log(acs_2018_black+1) + state_region, 
   data = d.pct_captions) %>%
  tidy() %>%
  mutate(term = case_when(
    grepl("state_division", term) ~ gsub("state_division","Division: ", term),
    grepl("state_region", term) ~ gsub("state_region","Region: ", term),
    grepl("n_vids", term) ~ gsub("n_vids","Number of Videos", term),
    grepl("acs_2018_white", term) ~ gsub("acs_2018_white","White Pop.", term),
    grepl("acs_2018_black", term) ~ gsub("acs_2018_black","Black Pop.", term),
    grepl("acs_2018_pop", term) ~ gsub("acs_2018_pop","Total Pop.", term),
    TRUE ~ term
  )) %>%
  ggplot(aes(y=term, x=estimate, xmin=estimate-2*std.error, xmax=estimate+2*std.error)) +
    geom_pointrange() + 
    geom_vline(xintercept = 0, lty = 2) +
    ylab("Predictor") +
    xlab("OLS Coefficient") +
    labs(caption = "DV: Logged Number of Captioned Videos") +
    theme_bw()
ggsave("out/caption_rate.pdf", height=4, width=4)

## ++ weighting demo ------------------------------------------------------

dat.places <- dat %>%
  distinct(st_fips)

dat.acs.places <- acs %>%
  select(NAME, st_fips = GEOID, total = totalpop, white = White, black = Black) %>%
  filter(total > 0, !is.na(total)) %>%
  mutate(st_fips = as.numeric(st_fips)) %>%
  left_join(dat.places %>% 
              mutate(in_sample = 1), by = "st_fips") %>%
  mutate(in_sample = coalesce(in_sample, 0))

make_binned <- function(., p = c(0, 0.33, 0.66, 1)) {
  q <- quantile(., probs = p, na.rm=T)
  q <- unique(q)
  cut(., breaks = q, include.lowest=TRUE)
}

dat.acs.places$total.binned <- make_binned(log(dat.acs.places$total+1))
dat.acs.places$white.binned <- make_binned(dat.acs.places$white/dat.acs.places$total)
dat.acs.places$black.binned <- make_binned(log((dat.acs.places$black/dat.acs.places$total)+1))

### rake weights

dat.acs.places.pop.mgns <- dat.acs.places %>%
  select(total.binned, white.binned, black.binned, st_fips, in_sample) %>%
  gather(key = "var", value = "val", total.binned, white.binned, black.binned) %>%
  arrange(st_fips, var, val) %>%
  group_by(var, val) %>%
  summarise(n=n(), .groups = "drop") %>%
  group_split(var) %>%
  lapply(., function(df) {
    df %>% 
      mutate(Freq = `n`/sum(`n`)) %>% 
      select(val, Freq) %>% 
      rename_at("val", ~ df$var[1])
  })
dat.acs.places.samp.mgns <- lapply(dat.acs.places.pop.mgns, 
                                   function(.) formula(paste0("~",colnames(.)[1])))

dat.acs.places$wt.init <- 1
dat.acs.places.dsgn <- 
  survey::svydesign(ids = ~1, 
                    data = dat.acs.places[dat.acs.places$in_sample == 1,], 
                    weights = dat.acs.places$wt.init[dat.acs.places$in_sample == 1])

dat.acs.places.raked <- 
  survey::rake(dat.acs.places.dsgn,
               population.margins = dat.acs.places.pop.mgns,
               sample.margins = dat.acs.places.samp.mgns)

### trim and normalize weights
wt.raked <- weights(dat.acs.places.raked)
wt.raked <- wt.raked * (length(wt.raked) / sum(wt.raked))
wt.raked <- scales::oob_squish(wt.raked, range=wt.raked.q)
wt.raked <- wt.raked * (length(wt.raked) / sum(wt.raked))
wt.raked.q <- quantile(wt.raked, probs=c(0.01, 0.99))
print(wt.raked.q)

dat.acs.places$wt.raked <- 0
dat.acs.places$wt.raked[dat.acs.places$in_sample == 1] <- wt.raked

### visualise
dat.acs.places.binned.wts <- dat.acs.places %>%
  mutate(wt.sampl = ifelse(in_sample, 1/sum(in_sample), 0),
         wt.raked = ifelse(in_sample, wt.raked/sum(wt.raked), 0)) %>%
  group_by(total.binned, white.binned, black.binned) %>%
  summarise(n.popl = n(),
            n.sampl = sum(wt.sampl)*nrow(dat.acs.places),
            n.raked = sum(wt.raked)*nrow(dat.acs.places),
            .groups = "drop")

dat.acs.places.binned.wts <-
  dat.acs.places.binned.wts %>%
  mutate(var = paste0("Pop (",as.numeric(total.binned),") x ",
                      "White (",as.numeric(white.binned),") x ",
                      "Black (",as.numeric(black.binned),")"))

dat.acs.places.binned.wts <- dat.acs.places.binned.wts %>%
  filter(n.popl > 100)
dat.acs.places.binned.wts %>%
  gather(key="type", value="n", n.raked, n.popl, n.sampl) %>%
  mutate(type = case_when(
    type == "n.popl" ~ "Population (U.S. Census)",
    type == "n.sampl" ~ "Sample",
    type == "n.raked" ~ "Weighted Sample"
  )) %>%
  ggplot(aes(x=n, y=var)) +
    geom_point(aes(group=type, color=type, shape=type), size=3) +
    geom_segment(data = dat.acs.places.binned.wts,
                 aes(x=n.popl, xend=n.raked, y=var, yend=var)) +
    theme_bw() +
    scale_x_continuous(name = "Count", labels = scales::comma_format(1)) +
    scale_y_discrete(name = "Type Locality by Binned Demographic Characteristics") +
    # guides(color=guide_legend(ncol=1, byrow=TRUE)) +
    theme(legend.position="top",
          legend.title = element_text(size=0))
ggsave("out/weights_demo.pdf", height=5.5, width=5.5)

