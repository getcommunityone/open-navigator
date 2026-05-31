# Pre-amble ---------------------------------------------------------------

library(ggplot2)
library(tidyverse)
library(sf)

# Read in data ------------------------------------------------------------

## ++ meetings
message("Reading in meeting data")
# meetings_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/meetings.rds" ## FASRC
meetings_fpath <- "meetings.rds" ## local

if (!"dat" %in% ls()) {
  dat <- readRDS(meetings_fpath) ## ~2 minutes
  print(paste0("n = ", nrow(dat)))
  print(table(`Meeting Years:`=substr(dat$meeting_date, 1, 4)))
}

## ++ geographies
message("Reading in geography data")

# geo_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/external/geo.txt" ## FASRC
geo_fpath <- "geo.txt"
geo <- read.delim(geo_fpath, stringsAsFactors=FALSE)

# geo_counties_fpath <- "/n/holyscratch01/enos_lab/sbarari/localview_data/external/county_centroids.rds" ## FASRC
geo_counties_fpath <- "county_centroids.rds"
geo_counties <- readRDS(geo_counties_fpath)


# Make map ----------------------------------------------------------------
message("Making map")

usa <- map_data("usa")

table(unique(dat$st_fips) %in% geo$GEOID)

dat %>%
  distinct(st_fips, place_name, state_name) %>%
  filter(!(st_fips %in% geo$GEOID))

geo2 <- bind_rows(
  geo %>%
    group_by(GEOID) %>%
    summarise(lat     = INTPTLAT[1],
              long    = INTPTLONG[1],
              .groups = "drop")
  ,
  geo_counties %>%
    as_tibble() %>%
    mutate(GEOID = as.numeric(GEOID)) %>%
    group_by(GEOID) %>%
    summarise(lat     = lat[1],
              long    = long[1],
              .groups = "drop")
) %>% 
  distinct()

dat_map <- dat %>%
  filter(!(state_name %in% c("Hawaii","Alaska"))) %>%
  mutate(GEOID=st_fips) %>%
  mutate(county = case_when(
    grepl("COUNTY", place_govt, ignore.case=T) ~ TRUE,
    grepl("county", place_name, ignore.case=T) ~ TRUE,
    TRUE ~ FALSE
  )) %>%
  distinct(GEOID, state_name, place_name, place_Pres_dem2pv, acs_2018_pop, county) %>%
  left_join(geo2, by = "GEOID") %>%
  group_by(GEOID, lat, long, county) %>% 
  summarise(counts  = n(),
            name    = place_name[1],
            state   = state_name[1],
            id      = GEOID[1],
            Pres.dem2pv_avg = mean(place_Pres_dem2pv, na.rm=T),
            pop     = acs_2018_pop[1],
            logpop  = log(pop[1]),
            .groups = "drop") %>%
  mutate(size = case_when(
    # county == TRUE ~ "county",
    pop >= 500000 ~ ">500k",
    pop <  500000 ~ "<500k"
  )) %>%
  mutate(size = factor(size, levels = c("<500k",">500k"))) %>%
  mutate(pres = ifelse(Pres.dem2pv_avg > 0.5, "D", "R")) %>%
  mutate(pres = factor(pres, levels = c("D","R")))  

table(is.na(dat$Pres.dem2pv_avg))
table(is.na(dat_map$pop))
table(is.na(dat_map$size))

# map <- ggplot(data = map_data("state")) + 
#   geom_polygon(aes(x = long, y = lat, group = group), 
#                color = "#4f464a", 
#                fill = "#eaecea") + 
#   coord_fixed(1.3) +
#   geom_point(data = dat_map %>%
#                filter(long > -160 & !is.na(pres)) %>% 
#                filter(size == "<250k"), 
#              aes(x = long, y = lat, 
#                  fill = pres, color = pres, shape = size, size = size, alpha = size)) +     
#   geom_point(data = dat_map %>%
#                filter(long > -160 & !is.na(pres)) %>% 
#                filter(size == ">250k"), 
#              aes(x = long, y = lat, 
#                  fill = pres, color = pres, shape = size, size = size, alpha = size)) + 
#   geom_point(data = dat_map %>%
#                filter(long > -160 & !is.na(pres)) %>% 
#                filter(size == "county"), 
#              aes(x = long, y = lat, 
#                  fill = pres, color = pres, shape = size, size = size, alpha = size)) +   
#   scale_fill_manual(values=c("#1155cc","#e0432b")) +
#   scale_colour_manual(values=c("#1155cc","#e0432b")) +
#   scale_shape_manual(values=c(16,18,17)) +
#   scale_alpha_manual(values=c(0.6, 1, 0.8)) +
#   scale_size_manual(values=c(3,5,6)) +
#   theme_map + 
#   theme(legend.position = "bottom")

dat_map$name <- gsub(" city", "", dat_map$name)

dat_map$state_abb <- state.abb[match(dat_map$state, state.name)]

dat_map$label <- paste(dat_map$name, ", ", dat_map$state_abb, sep = "")

# Manually fix Nashville
dat_map$label[dat_map$GEOID == "4752006"] <- "Nashville, TN"

theme_map <- theme_void() + 
  theme(plot.title = element_text(size = 30, hjust = 0.5), 
        panel.border = element_blank(), 
        panel.grid.major = element_blank(),
        panel.grid.minor = element_blank(),
        legend.title = element_text(size = 0),
        legend.text = element_text(size = 12),
        axis.title = element_text(size = 0),
        axis.text = element_text(size = 0))

dat_map %>%
  distinct(state, name, county, GEOID) %>%
  group_by(GEOID) %>%
  filter(length(unique(county)) > 1) %>%
  ungroup() %>%
  filter(county == TRUE) %>%
  left_join(dat %>%
    mutate(county = case_when(
      grepl("COUNTY", place_govt, ignore.case=T) ~ TRUE,
      grepl("county", place_name, ignore.case=T) ~ TRUE,
      TRUE ~ FALSE
    )) %>%
    mutate(place_name = gsub(" city", "", place_name)) %>%
    filter(county == TRUE) %>%
    select(state=state_name, name=place_name, vid_title) %>%
    distinct(state, name, .keep_all = TRUE)) %>%
  as.data.frame()

ggplot(data = map_data("state")) + 
  geom_polygon(aes(x = long, y = lat, group = group), 
               color = "white", 
               fill = "#EAE0D5") + 
  # Exterior border
  geom_polygon(data = map_data("usa"), 
               aes(x = long, y = lat, group = group), 
               color = "#22333B", fill = NA) + 
  coord_fixed(1.3) +
  geom_point(data = dat_map %>%
               filter(long > -160 & county == FALSE) %>% 
               filter(size == "<500k"), 
             aes(x = long, y = lat, 
                 size = size, color = size, fill = size,
                 alpha = size, shape = county)) +     
  geom_point(data = dat_map %>%
               filter(long > -160 & county == FALSE) %>%
               filter(size == ">500k"),
             aes(x = long, y = lat,
                 size = size, color = size, fill = size,
                 alpha = size, shape = county)) +
  geom_point(data = dat_map %>%
               filter(long > -160 & county == TRUE),
             aes(x = long, y = lat, 
                 size = size, color = size,
                 alpha = size, shape = county), stroke = 1) +   
  ggrepel::geom_label_repel(data = dat_map %>%
               filter(long > -160 & !is.na(county) & pop > 500000 & county == FALSE),
             aes(x = long, y = lat, label = label),
             fill = alpha(c("white"),0.8), 
             fontface = "bold") +
  scale_fill_manual(name = "Population:", values=c("#22333B","#C83E4D")) +
  scale_colour_manual(name = "Population:", values=c("#22333B","#C83E4D")) +
  scale_shape_manual(name = "Jurisdiction:", values=c(20, 24), 
                     labels = c("city", "county")) +
  scale_alpha_manual(name = "Population:", values=c(0.5, 1)) +
  scale_size_manual(name = "Population:", values=c(3,8)) +
  theme_map + 
  guides(shape = guide_legend(nrow = 2, override.aes = list(size = 4)),
         fill = guide_legend(nrow = 2)) + 
  theme(legend.position = "bottom")

ggsave("map_test.png", width = 8, height = 4)

# Save --------------------------------------------------------------------

ggsave(map, filename = sprintf("out/map.pdf"), width = 11, height = 8.5)
ggsave(map, filename = sprintf("out/map.png"), width = 11, height = 8.5)

if (!grepl("rc.fas.harvard.edu", Sys.info()[4])){
  system(sprintf("open out/map.pdf"))
}

map_txt <- bind_rows(
  dat_map %>%
    mutate(type = paste0("pres vote: ", pres)) %>%
    group_by(type) %>%
    summarise(places = n(), 
              towns = sum(!grepl("county", name, ignore.case = TRUE)),
              counties = sum(grepl("county", name, ignore.case = TRUE)),
              .groups = "drop")
  ,
  dat_map %>%
    mutate(type = ifelse(is.na(lat), "not in map", "in map")) %>%
    group_by(type) %>%
    summarise(places = n(), 
              towns = sum(!grepl("county", name, ignore.case = TRUE)),
              counties = sum(grepl("county", name, ignore.case = TRUE)),
              .groups = "drop")  
  ,
  dat_map %>%
    mutate(type = paste0("popl: ", size)) %>%
    group_by(type) %>%
    summarise(places = n(), 
              towns = sum(!grepl("county", name, ignore.case = TRUE)),
              counties = sum(grepl("county", name, ignore.case = TRUE)),
              .groups = "drop")
)
write_delim(map_txt, file = "out/map.txt", delim = "|")
