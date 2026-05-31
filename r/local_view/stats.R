# Pre-amble ---------------------------------------------------------------

library(tidyverse)

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

## ++ geography
geo_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/external/geo.txt" ## FASRC
# geo_fpath <- "geo.txt"
geo <- read.delim(geo_fpath, stringsAsFactors=FALSE)

# Calculate stats ---------------------------------------------------------

message(paste("Num meetings:", nrow(dat)))
message(paste("Num meetings with captions:", sum(!is.na(dat$caption_text))))
message(paste("Num channels:", length(unique(dat$channel_id))))
message(paste("Num governments:", length(unique(paste(dat$st_fips, dat$place_govt)))))
message(paste("Num places:", length(unique(dat$st_fips))))
message(paste("Num counties:", length(unique(dat$place_name)[grepl("county", unique(dat$place_name), ignore.case = T)])))
message(paste("Num states:", length(unique(dat$state_name))))

distinct(dat, place_name, acs_2018_pop) %>%
  filter(!grepl("county", place_name, ignore.case = T)) %>%
  with(., print(summary(acs_2018_pop)))
distinct(dat, place_name, acs_2018_pop) %>%
  filter(!grepl("county", place_name, ignore.case = T)) %>%
  with(., print(table(`Muncipalities w/ACS 2018 population >500k`=acs_2018_pop > 500000)))
distinct(dat, place_name, acs_2018_pop) %>%
  filter(!grepl("county", place_name, ignore.case = T)) %>%
  with(., print(prop.table(table(`Muncipalities w/ACS 2018 population >500k`=acs_2018_pop > 500000))))

distinct(dat, place_name, acs_2018_pop) %>%
  filter(!grepl("county", place_name, ignore.case = T)) %>%
  with(., print(table(`Muncipalities w/ACS 2018 population >1mil`=acs_2018_pop > 1000000)))
distinct(dat, place_name, acs_2018_pop) %>%
  filter(!grepl("county", place_name, ignore.case = T)) %>%
  with(., print(prop.table(table(`Muncipalities w/ACS 2018 population >1mil`=acs_2018_pop > 1000000))))

print(table(`Places with >500k population:`=geo$POP10 > 500000))
print(table(`Places with >1mil population:`=geo$POP10 > 1000000))

print(summary(geo$POP10))


message(paste0("Num meetings where upload date differs from meeting date: ", 
               sum(dat$meeting_date == dat$vid_upload_date),
               " (",round(mean(dat$meeting_date == dat$vid_upload_date),2),")"))
prop.table(table(`Diff b/t meeting date and upload date is 1:`=
                   abs(dat$vid_upload_date - dat$meeting_date) == 1))
prop.table(table(`Diff b/t meeting date and upload date <= 3:`=
                   abs(dat$vid_upload_date - dat$meeting_date) <= 3))
prop.table(table(`Diff b/t meeting date and upload date <= 14:`=
                   abs(dat$vid_upload_date - dat$meeting_date) <= 14))
prop.table(table(`Diff b/t meeting date and upload date is <=3 (for meetings that diff):`=
                   abs(dat$vid_upload_date - dat$meeting_date)[dat$vid_upload_date != dat$meeting_date] <= 3))
prop.table(table(`Diff b/t meeting date and upload date is <=30 (for meetings that diff):`=
                   abs(dat$vid_upload_date - dat$meeting_date)[dat$vid_upload_date != dat$meeting_date] <= 30))

# Keyword checks ----------------------------------------------------------

kwd.zoning_planning <- grepl("(zoning|planning)", dat$caption_text, perl=TRUE)
kwd.school <- grepl("school", dat$caption_text, perl=TRUE)
kwd.county <- grepl("county", dat$caption_text, perl=TRUE)

prop.table(table(dat$place_govt, kwd.zoning_planning), 1)
prop.table(table(dat$place_govt, kwd.school), 1)
prop.table(table(dat$place_govt, kwd.county), 1)

